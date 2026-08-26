"""The conversation engine: one turn in, one agent reply out.

Pipeline per customer utterance:

    persist -> NLU (rules + LLM) -> memory merge -> ensemble scoring
            -> action decisions -> background execution
            -> response generation (LLM, template fallback) -> broadcast

Every stage degrades instead of failing: no LLM, no classifier, no WhatsApp
credentials - the call still completes and still produces a scored lead.
"""
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.events import bus
from app.core.logging import get_logger
from app.models import (
    Action,
    Call,
    CallTranscript,
    ConversationMessage,
    Customer,
    Lead,
    LeadScore,
)
from app.schemas.nlu import CustomerMemory, TurnExtraction
from app.services import config_service
from app.services.actions import engine as action_engine
from app.services.classification import ensemble
from app.services.conversation import extractor
from app.services.conversation.knowledge import FAQRetriever
from app.services.conversation.prompts import SUMMARY_SYSTEM, build_system_prompt
from app.services.conversation.responder import TemplateResponder
from app.services.llm.factory import get_llm
from app.utils.text import normalize

log = get_logger(__name__)

STAGE_ORDER = ["opening", "discovery", "qualification", "objection", "action", "closing"]

# The agent always greets in English and then mirrors whatever language the
# customer actually replies in - detected per turn by the NLU layer. We never
# guess the customer's language up front.
OPENING_LANGUAGE = "english"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConversationEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.profile = config_service.get_profile(db)
        self.weights = config_service.get_weights(db)
        self.thresholds = config_service.get_thresholds(db)
        self.faq = FAQRetriever(config_service.get_faq(db))
        self.responder = TemplateResponder(self.profile)
        self.llm = get_llm()

    # ------------------------------------------------------------------
    # Call lifecycle
    # ------------------------------------------------------------------

    async def start_call(
        self,
        customer: Customer,
        mode: str = "demo",
        provider: str = "mock",
        campaign_id: Optional[int] = None,
        provider_call_sid: Optional[str] = None,
    ) -> Tuple[Call, str]:
        lead = self._get_or_create_lead(customer)

        call = Call(
            customer_id=customer.id,
            lead_id=lead.id,
            campaign_id=campaign_id,
            mode=mode,
            provider=provider,
            provider_call_sid=provider_call_sid,
            status="active",
            conversation_stage="opening",
        )
        self.db.add(call)
        self.db.commit()
        self.db.refresh(call)

        opening = self.responder.opening(customer.name, OPENING_LANGUAGE)
        self._add_message(call, "agent", opening, language=OPENING_LANGUAGE)
        self.db.commit()

        await bus.broadcast(
            "call.started",
            {
                "call_id": call.id,
                "customer": {
                    "id": customer.id,
                    "name": customer.name,
                    "phone_number": customer.phone_number,
                    "language": customer.preferred_language,
                },
                "mode": mode,
                "provider": provider,
                "agent_message": opening,
                "lead_id": lead.id,
            },
            call_id=call.id,
        )
        await bus.broadcast(
            "message.agent", {"call_id": call.id, "role": "agent", "content": opening}, call_id=call.id
        )
        return call, opening

    async def handle_turn(self, call: Call, user_text: str) -> Dict[str, Any]:
        """Process one customer utterance and return everything the UI needs."""
        started = time.perf_counter()
        text = normalize(user_text)
        customer = self.db.get(Customer, call.customer_id)
        lead = self._get_or_create_lead(customer)

        await bus.broadcast(
            "message.customer",
            {"call_id": call.id, "role": "customer", "content": text},
            call_id=call.id,
        )

        # 1. Understand
        turn, nlu_debug = await extractor.extract(text, llm=self.llm)

        # 2. Remember
        memory = CustomerMemory(**(lead.memory or {}))
        memory.phone_number = customer.phone_number
        memory.customer_name = memory.customer_name or customer.name
        memory.merge_turn(turn)

        # 3. Score (rules + trained classifier + LLM)
        transcript = self._transcript_messages(call)
        transcript.append({"role": "customer", "content": text})
        history = self._turn_history(call) + [turn]

        verdict = await ensemble.classify(
            memory=memory,
            turns=history,
            last_utterance=text,
            transcript=transcript,
            llm=self.llm,
            weights=self.weights,
            thresholds=self.thresholds,
        )
        memory.lead_score = verdict["score"]
        memory.lead_status = verdict["classification"]

        self._persist_turn(call, lead, customer, text, turn, verdict, memory)

        await bus.broadcast(
            "lead.updated",
            {
                "call_id": call.id,
                "lead_id": lead.id,
                "score": verdict["score"],
                "classification": verdict["classification"],
                "reasons": verdict["reasons"],
                "signals": verdict["signals"],
                "memory": memory.to_json(),
                "ensemble": verdict["ensemble_detail"],
                "extracted": turn.model_dump(mode="json"),
            },
            call_id=call.id,
        )

        # 4. Act (decide now, execute in the background)
        already_done = [a.action_type for a in self.db.query(Action).filter(Action.call_id == call.id)]
        decisions = action_engine.decide(turn, memory, verdict["classification"], already_done)
        actions = await action_engine.dispatch(
            self.db, call, lead, customer, memory, verdict["classification"], decisions, self.profile
        )

        # 5. Reply
        stage = self._next_stage(call, turn, verdict["classification"], actions)
        call.conversation_stage = stage
        reply = await self._generate_reply(
            call, memory, turn, stage, actions, transcript, already_done
        )

        self._add_message(
            call,
            "agent",
            reply,
            language=memory.language,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

        should_end = any(a["action_type"] == action_engine.END_CALL for a in actions)
        call.turn_count += 1
        call.final_score = verdict["score"]
        call.final_status = verdict["classification"]
        self.db.commit()

        await bus.broadcast(
            "message.agent",
            {"call_id": call.id, "role": "agent", "content": reply, "stage": stage},
            call_id=call.id,
        )

        if should_end:
            await self.end_call(call, outcome="closed_by_customer")

        return {
            "call_id": call.id,
            "reply": reply,
            "stage": stage,
            "should_end": should_end,
            "extracted": turn.model_dump(mode="json"),
            "memory": memory.to_json(),
            "lead": {
                "id": lead.id,
                "score": verdict["score"],
                "classification": verdict["classification"],
                "reasons": verdict["reasons"],
                "signals": verdict["signals"],
            },
            "ensemble": verdict["ensemble_detail"],
            "actions": actions,
            "nlu_debug": nlu_debug,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }

    async def end_call(self, call: Call, outcome: str = "completed") -> Dict[str, Any]:
        if call.status == "completed":
            return {"call_id": call.id, "status": "completed", "summary": call.summary}

        call.status = "completed"
        call.outcome = outcome
        call.ended_at = utcnow()
        started = call.started_at
        if started is not None:
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            call.duration_seconds = max(0, int((call.ended_at - started).total_seconds()))

        transcript_text = self._transcript_text(call)
        existing = self.db.query(CallTranscript).filter(CallTranscript.call_id == call.id).first()
        if existing:
            existing.text = transcript_text
            existing.word_count = len(transcript_text.split())
        else:
            self.db.add(
                CallTranscript(
                    call_id=call.id, text=transcript_text, word_count=len(transcript_text.split())
                )
            )

        call.summary = await self._summarise(call, transcript_text)
        self.db.commit()

        await bus.broadcast(
            "call.ended",
            {
                "call_id": call.id,
                "outcome": outcome,
                "duration_seconds": call.duration_seconds,
                "final_score": call.final_score,
                "final_status": call.final_status,
                "summary": call.summary,
                "turn_count": call.turn_count,
            },
            call_id=call.id,
        )
        return {
            "call_id": call.id,
            "status": "completed",
            "summary": call.summary,
            "final_score": call.final_score,
            "final_status": call.final_status,
        }

    # ------------------------------------------------------------------
    # Response generation
    # ------------------------------------------------------------------

    async def _generate_reply(
        self,
        call: Call,
        memory: CustomerMemory,
        turn: TurnExtraction,
        stage: str,
        actions: List[Dict[str, Any]],
        transcript: List[Dict[str, str]],
        already_done: Optional[List[str]] = None,
    ) -> str:
        faq_answer = (
            self.faq.best_answer(turn.asked_question, memory.language)
            if turn.asked_question
            else None
        )
        fallback = self.responder.reply(memory, turn, stage, faq_answer, actions, already_done)

        if not self.llm.available:
            return fallback

        action_note = self._action_note(actions)
        knowledge = self.faq.as_context(turn.asked_question or "", top_k=2)

        system = build_system_prompt(self.profile, memory, stage)
        if knowledge:
            system += f"\n\nSTORE FACTS RELEVANT RIGHT NOW:\n{knowledge}"
        if action_note:
            system += (
                f"\n\nIMPORTANT: you have JUST done this - mention it naturally in your reply: {action_note}"
            )

        messages = [{"role": "system", "content": system}]
        for message in transcript[-8:]:
            role = "assistant" if message["role"] == "agent" else "user"
            messages.append({"role": role, "content": message["content"]})

        try:
            reply = await self.llm.chat(messages, temperature=0.7, max_tokens=140)
            reply = normalize(reply).strip('"').strip()
            if not reply or len(reply) > 600:
                return fallback
            return reply
        except Exception as exc:  # noqa: BLE001
            log.warning("LLM reply failed (%s); using template responder", exc)
            return fallback

    @staticmethod
    def _action_note(actions: List[Dict[str, Any]]) -> str:
        notes = []
        for action in actions:
            if action["action_type"] == action_engine.SEND_WHATSAPP:
                notes.append("sent the collection to their WhatsApp")
            elif action["action_type"] == action_engine.SCHEDULE_CALLBACK:
                when = (action.get("result") or {}).get("human_time")
                notes.append(f"booked a callback for {when}" if when else "booked a callback")
            elif action["action_type"] == action_engine.MARK_DNC:
                notes.append("removed their number from the calling list")
        return "; ".join(notes)

    async def _summarise(self, call: Call, transcript_text: str) -> str:
        lead = self.db.get(Lead, call.lead_id) if call.lead_id else None
        memory = CustomerMemory(**(lead.memory or {})) if lead else CustomerMemory()

        if self.llm.available and call.turn_count > 0:
            try:
                summary = await self.llm.chat(
                    [
                        {"role": "system", "content": SUMMARY_SYSTEM},
                        {"role": "user", "content": transcript_text[-3000:]},
                    ],
                    temperature=0.3,
                    max_tokens=120,
                )
                if summary.strip():
                    return normalize(summary)
            except Exception as exc:  # noqa: BLE001
                log.debug("LLM summary failed: %s", exc)

        bits: List[str] = []
        if memory.intent:
            bits.append("Interested in " + ", ".join(i.replace("_", " ") for i in memory.intent))
        if memory.clothing_categories or memory.brands:
            bits.append("Looking for " + ", ".join(memory.brands + memory.clothing_categories))
        if memory.budget:
            bits.append(f"Budget Rs.{memory.budget}")
        if memory.timeline:
            bits.append(f"Timeline: {memory.timeline.replace('_', ' ')}")
        if memory.barriers:
            bits.append("Blockers: " + ", ".join(b.replace("_", " ") for b in memory.barriers))
        if memory.callback_requested:
            bits.append("Callback requested")
        summary = ". ".join(bits) if bits else "No qualifying information captured."
        return f"{summary}. Final status: {call.final_status} ({call.final_score}/100)."

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _get_or_create_lead(self, customer: Customer) -> Lead:
        lead = (
            self.db.query(Lead)
            .filter(Lead.customer_id == customer.id)
            .order_by(Lead.id.desc())
            .first()
        )
        if lead is None:
            lead = Lead(customer_id=customer.id, memory=CustomerMemory(
                customer_name=customer.name,
                phone_number=customer.phone_number,
                language=customer.preferred_language or "english",
            ).to_json())
            self.db.add(lead)
            self.db.commit()
            self.db.refresh(lead)
        return lead

    def _add_message(
        self,
        call: Call,
        role: str,
        content: str,
        language: Optional[str] = None,
        intent: Optional[str] = None,
        sentiment: Optional[str] = None,
        extracted: Optional[Dict[str, Any]] = None,
        score_after: Optional[int] = None,
        latency_ms: Optional[int] = None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            call_id=call.id,
            role=role,
            content=content,
            language=language,
            intent=intent,
            sentiment=sentiment,
            extracted=extracted or {},
            score_after=score_after,
            latency_ms=latency_ms,
        )
        self.db.add(message)
        return message

    def _persist_turn(
        self,
        call: Call,
        lead: Lead,
        customer: Customer,
        text: str,
        turn: TurnExtraction,
        verdict: Dict[str, Any],
        memory: CustomerMemory,
    ) -> None:
        self._add_message(
            call,
            "customer",
            text,
            language=turn.language,
            intent=turn.intent,
            sentiment=turn.sentiment,
            extracted=turn.model_dump(mode="json"),
            score_after=verdict["score"],
        )

        lead.memory = memory.to_json()
        lead.status = verdict["classification"]
        lead.score = verdict["score"]
        lead.score_reasons = verdict["reasons"]
        lead.intent = memory.intent
        lead.budget = memory.budget
        lead.currency = memory.currency
        lead.clothing_categories = memory.clothing_categories
        lead.brands = memory.brands
        lead.size = memory.size
        lead.timeline = memory.timeline
        lead.location = memory.location
        lead.barriers = memory.barriers
        lead.sentiment = memory.sentiment
        lead.language = memory.language
        lead.last_interaction_at = utcnow()

        if memory.customer_name and not customer.name:
            customer.name = memory.customer_name
        if memory.location and not customer.city:
            customer.city = memory.location
        customer.preferred_language = memory.language

        self.db.add(
            LeadScore(
                lead_id=lead.id,
                call_id=call.id,
                score=verdict["score"],
                classification=verdict["classification"],
                reasons=verdict["reasons"],
                signals=verdict["signals"],
                rules_label=verdict.get("rules_label"),
                ml_label=verdict.get("ml_label"),
                ml_confidence=verdict.get("ml_confidence"),
                llm_label=verdict.get("llm_label"),
                ensemble_detail=verdict.get("ensemble_detail", {}),
            )
        )
        self.db.commit()

    def _transcript_messages(self, call: Call) -> List[Dict[str, str]]:
        messages = (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.call_id == call.id)
            .order_by(ConversationMessage.id)
            .all()
        )
        return [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]

    def _turn_history(self, call: Call) -> List[TurnExtraction]:
        messages = (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.call_id == call.id, ConversationMessage.role == "customer")
            .order_by(ConversationMessage.id)
            .all()
        )
        history: List[TurnExtraction] = []
        for message in messages:
            if message.extracted:
                try:
                    history.append(TurnExtraction(**message.extracted))
                except Exception:  # noqa: BLE001 - old rows should never break a live call
                    continue
        return history

    def _transcript_text(self, call: Call) -> str:
        lines = []
        for message in self._transcript_messages(call):
            speaker = "AGENT" if message["role"] == "agent" else "CUSTOMER"
            lines.append(f"{speaker}: {message['content']}")
        return "\n".join(lines)

    def _next_stage(
        self,
        call: Call,
        turn: TurnExtraction,
        classification: str,
        actions: List[Dict[str, Any]],
    ) -> str:
        if any(a["action_type"] == action_engine.END_CALL for a in actions):
            return "closing"
        if turn.barriers:
            return "objection"
        if any(a["action_type"] in (action_engine.SEND_WHATSAPP, action_engine.SCHEDULE_CALLBACK) for a in actions):
            return "action"
        if classification == "HOT":
            return "action"
        if call.conversation_stage in ("opening", "discovery"):
            return "discovery" if not turn.intent or turn.intent in ("greeting", "other") else "qualification"
        return "qualification"

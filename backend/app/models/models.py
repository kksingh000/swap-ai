"""SQLAlchemy models. Works identically on SQLite (local) and PostgreSQL (prod)."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(120))
    phone_number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(160))
    city: Mapped[Optional[str]] = mapped_column(String(80))
    preferred_language: Mapped[str] = mapped_column(String(16), default="english")
    do_not_call: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    leads: Mapped[List["Lead"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    calls: Mapped[List["Call"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    campaign_type: Mapped[str] = mapped_column(String(40), default="acquisition")
    goal: Mapped[Optional[str]] = mapped_column(Text)
    opening_line: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Lead(Base, TimestampMixin):
    """One lead per customer: the rolling structured picture of what they want."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )

    status: Mapped[str] = mapped_column(String(16), default="UNKNOWN", index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    score_reasons: Mapped[List[str]] = mapped_column(JSON, default=list)

    # The live customer-memory object, updated after every utterance.
    memory: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    intent: Mapped[List[str]] = mapped_column(JSON, default=list)
    budget: Mapped[Optional[int]] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    clothing_categories: Mapped[List[str]] = mapped_column(JSON, default=list)
    brands: Mapped[List[str]] = mapped_column(JSON, default=list)
    size: Mapped[Optional[str]] = mapped_column(String(24))
    timeline: Mapped[Optional[str]] = mapped_column(String(40))
    location: Mapped[Optional[str]] = mapped_column(String(120))
    barriers: Mapped[List[str]] = mapped_column(JSON, default=list)
    sentiment: Mapped[str] = mapped_column(String(16), default="neutral")
    language: Mapped[str] = mapped_column(String(16), default="english")
    last_interaction_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    customer: Mapped["Customer"] = relationship(back_populates="leads")
    scores: Mapped[List["LeadScore"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )


class Call(Base, TimestampMixin):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    lead_id: Mapped[Optional[int]] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    campaign_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL")
    )

    mode: Mapped[str] = mapped_column(String(16), default="demo")
    provider: Mapped[str] = mapped_column(String(24), default="mock")
    provider_call_sid: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    direction: Mapped[str] = mapped_column(String(16), default="outbound")
    status: Mapped[str] = mapped_column(String(24), default="initiated", index=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(40))

    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    final_score: Mapped[int] = mapped_column(Integer, default=0)
    final_status: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    summary: Mapped[Optional[str]] = mapped_column(Text)
    conversation_stage: Mapped[str] = mapped_column(String(32), default="opening")

    customer: Mapped["Customer"] = relationship(back_populates="calls")
    messages: Mapped[List["ConversationMessage"]] = relationship(
        back_populates="call",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.id",
    )
    actions: Mapped[List["Action"]] = relationship(
        back_populates="call", cascade="all, delete-orphan"
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    language: Mapped[Optional[str]] = mapped_column(String(16))
    intent: Mapped[Optional[str]] = mapped_column(String(40))
    sentiment: Mapped[Optional[str]] = mapped_column(String(16))
    extracted: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    score_after: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    call: Mapped["Call"] = relationship(back_populates="messages")


class CallTranscript(Base):
    """Flattened human-readable transcript snapshot, written when a call ends."""

    __tablename__ = "call_transcripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), unique=True)
    text: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LeadScore(Base):
    """Every scoring decision is stored so the dashboard can explain itself."""

    __tablename__ = "lead_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    call_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), index=True
    )

    score: Mapped[int] = mapped_column(Integer, default=0)
    classification: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    reasons: Mapped[List[str]] = mapped_column(JSON, default=list)
    signals: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    rules_label: Mapped[Optional[str]] = mapped_column(String(16))
    ml_label: Mapped[Optional[str]] = mapped_column(String(16))
    ml_confidence: Mapped[Optional[float]] = mapped_column(Float)
    llm_label: Mapped[Optional[str]] = mapped_column(String(16))
    ensemble_detail: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="scores")


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), index=True
    )
    lead_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True
    )

    action_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    trigger_reason: Mapped[Optional[str]] = mapped_column(Text)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    call: Mapped[Optional["Call"]] = relationship(back_populates="actions")


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    call_id: Mapped[Optional[int]] = mapped_column(ForeignKey("calls.id", ondelete="SET NULL"))
    action_id: Mapped[Optional[int]] = mapped_column(ForeignKey("actions.id", ondelete="SET NULL"))

    to_number: Mapped[str] = mapped_column(String(24))
    body: Mapped[str] = mapped_column(Text)
    media_url: Mapped[Optional[str]] = mapped_column(String(400))
    template_kind: Mapped[Optional[str]] = mapped_column(String(24))
    provider: Mapped[str] = mapped_column(String(24), default="mock")
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Callback(Base):
    __tablename__ = "callbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    lead_id: Mapped[Optional[int]] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    call_id: Mapped[Optional[int]] = mapped_column(ForeignKey("calls.id", ondelete="SET NULL"))

    original_text: Mapped[Optional[str]] = mapped_column(Text)
    scheduled_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    timezone_name: Mapped[str] = mapped_column(String(40), default="Asia/Kolkata")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    interpretation: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DoNotCallEntry(Base):
    __tablename__ = "do_not_call_list"
    __table_args__ = (UniqueConstraint("phone_number", name="uq_dnc_phone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(24), index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(24), default="call")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StoreConfiguration(Base, TimestampMixin):
    """Single-row table holding the editable store profile and scoring weights."""

    __tablename__ = "store_configuration"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    scoring_weights: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    thresholds: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    faq: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)

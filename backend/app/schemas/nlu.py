"""Pydantic contracts for everything the NLU layer produces.

The LLM is *asked* for this shape and the deterministic extractor *builds* this
shape, so downstream code has exactly one thing to reason about.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

INTENTS = [
    "buy_thrift_clothes",
    "sell_clothes",
    "swap_clothes",
    "donate_clothes",
    "request_catalog",
    "request_store_visit",
    "request_callback",
    "learn_more",
    "just_browsing",
    "not_interested",
    "do_not_call",
    "objection",
    "question",
    "greeting",
    "other",
]

TIMELINES = ["today", "this_week", "this_month", "later", "exploring", "unknown"]
LANGUAGES = ["english", "hindi", "hinglish"]
SENTIMENTS = ["positive", "neutral", "negative"]


class BudgetInfo(BaseModel):
    amount: Optional[int] = None
    currency: str = "INR"
    qualifier: Optional[str] = None  # under | around | above | unknown

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v: Any) -> Optional[int]:
        if v in (None, "", "null"):
            return None
        try:
            return int(float(str(v).replace(",", "").replace("₹", "").strip()))
        except (TypeError, ValueError):
            return None


class TurnExtraction(BaseModel):
    """Structured understanding of a single customer utterance."""

    model_config = ConfigDict(extra="ignore")

    language: str = "english"
    intent: str = "other"
    secondary_intents: List[str] = Field(default_factory=list)
    budget: BudgetInfo = Field(default_factory=BudgetInfo)
    product_categories: List[str] = Field(default_factory=list)
    brands: List[str] = Field(default_factory=list)
    size: Optional[str] = None
    gender_preference: Optional[str] = None
    urgency: str = "unknown"
    location: Optional[str] = None
    barriers: List[str] = Field(default_factory=list)
    customer_name: Optional[str] = None
    sentiment: str = "neutral"
    buying_intent: float = 0.0
    requires_whatsapp: bool = False
    requires_callback: bool = False
    callback_time_text: Optional[str] = None
    asked_question: Optional[str] = None
    wants_to_end_call: bool = False
    do_not_call: bool = False
    source: str = "rules"  # rules | llm | merged

    @field_validator("language")
    @classmethod
    def _lang(cls, v: str) -> str:
        v = (v or "english").lower().strip()
        return v if v in LANGUAGES else "english"

    @field_validator("intent")
    @classmethod
    def _intent(cls, v: str) -> str:
        v = (v or "other").lower().strip()
        return v if v in INTENTS else "other"

    @field_validator("urgency")
    @classmethod
    def _urgency(cls, v: str) -> str:
        v = (v or "unknown").lower().strip().replace(" ", "_")
        return v if v in TIMELINES else "unknown"

    @field_validator("sentiment")
    @classmethod
    def _sentiment(cls, v: str) -> str:
        v = (v or "neutral").lower().strip()
        return v if v in SENTIMENTS else "neutral"

    @field_validator("buying_intent", mode="before")
    @classmethod
    def _intent_score(cls, v: Any) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.0

    @field_validator("product_categories", "brands", "barriers", "secondary_intents", mode="before")
    @classmethod
    def _listify(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, list):
            return [str(x).strip().lower() for x in v if str(x).strip()]
        return []


class CustomerMemory(BaseModel):
    """The rolling picture of the customer, persisted on the lead row."""

    model_config = ConfigDict(extra="ignore")

    customer_name: Optional[str] = None
    phone_number: Optional[str] = None
    intent: List[str] = Field(default_factory=list)
    budget: Optional[int] = None
    budget_qualifier: Optional[str] = None
    currency: str = "INR"
    clothing_categories: List[str] = Field(default_factory=list)
    brands: List[str] = Field(default_factory=list)
    size: Optional[str] = None
    gender_preference: Optional[str] = None
    timeline: Optional[str] = None
    location: Optional[str] = None
    barriers: List[str] = Field(default_factory=list)
    features_requested: List[str] = Field(default_factory=list)
    questions_asked: List[str] = Field(default_factory=list)
    callback_requested: bool = False
    callback_time: Optional[str] = None
    language: str = "english"
    sentiment: str = "neutral"
    do_not_call: bool = False
    lead_score: int = 0
    lead_status: str = "UNKNOWN"

    def merge_turn(self, turn: TurnExtraction) -> "CustomerMemory":
        """Additive merge - later turns refine but never blank out what we know."""

        def add_all(existing: List[str], incoming: List[str]) -> List[str]:
            out = list(existing)
            for item in incoming:
                if item and item not in out:
                    out.append(item)
            return out

        if turn.intent not in ("other", "greeting", "question", "objection"):
            self.intent = add_all(self.intent, [turn.intent])
        self.intent = add_all(self.intent, [i for i in turn.secondary_intents if i in INTENTS])

        if turn.budget.amount:
            self.budget = turn.budget.amount
            self.budget_qualifier = turn.budget.qualifier
            self.currency = turn.budget.currency
        if turn.product_categories:
            self.clothing_categories = add_all(self.clothing_categories, turn.product_categories)
        if turn.brands:
            self.brands = add_all(self.brands, turn.brands)
        if turn.size:
            self.size = turn.size
        if turn.gender_preference:
            self.gender_preference = turn.gender_preference
        if turn.urgency != "unknown":
            self.timeline = turn.urgency
        if turn.location:
            self.location = turn.location
        if turn.barriers:
            self.barriers = add_all(self.barriers, turn.barriers)
        # Never overwrite a name we already have: the caller record is more
        # reliable than a mid-sentence guess.
        if turn.customer_name and not self.customer_name:
            self.customer_name = turn.customer_name
        if turn.asked_question:
            self.questions_asked = add_all(self.questions_asked, [turn.asked_question])
        if turn.requires_whatsapp:
            self.features_requested = add_all(self.features_requested, ["whatsapp_catalog"])
        if turn.requires_callback:
            self.callback_requested = True
        if turn.callback_time_text:
            self.callback_time = turn.callback_time_text
        if turn.do_not_call:
            self.do_not_call = True

        self.language = turn.language
        self.sentiment = turn.sentiment
        return self

    def to_json(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

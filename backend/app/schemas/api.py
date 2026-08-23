"""Request/response contracts for the REST API."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Calls
# --------------------------------------------------------------------------

class StartCallRequest(BaseModel):
    customer_name: Optional[str] = Field(default=None, max_length=120)
    phone_number: str = Field(min_length=6, max_length=24)
    campaign_type: str = "acquisition"
    language: str = "english"

    @field_validator("phone_number")
    @classmethod
    def _clean_phone(cls, v: str) -> str:
        cleaned = "".join(ch for ch in v if ch.isdigit() or ch == "+")
        if len(cleaned) < 6:
            raise ValueError("phone_number looks invalid")
        return cleaned


class StartDemoCallRequest(BaseModel):
    customer_name: Optional[str] = None
    phone_number: Optional[str] = None
    language: str = "english"
    scenario: Optional[str] = None


class TurnRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class TurnResponse(BaseModel):
    call_id: int
    reply: str
    stage: str
    should_end: bool
    extracted: Dict[str, Any]
    memory: Dict[str, Any]
    lead: Dict[str, Any]
    ensemble: Dict[str, Any]
    actions: List[Dict[str, Any]]
    latency_ms: int
    nlu_debug: Dict[str, Any] = {}


class MessageOut(ORMModel):
    id: int
    role: str
    content: str
    language: Optional[str] = None
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    score_after: Optional[int] = None
    latency_ms: Optional[int] = None
    created_at: datetime


class CallOut(ORMModel):
    id: int
    customer_id: int
    lead_id: Optional[int] = None
    mode: str
    provider: str
    provider_call_sid: Optional[str] = None
    status: str
    outcome: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    turn_count: int
    final_score: int
    final_status: str
    summary: Optional[str] = None
    conversation_stage: str


class CallDetail(CallOut):
    customer_name: Optional[str] = None
    phone_number: Optional[str] = None
    messages: List[MessageOut] = []
    actions: List[Dict[str, Any]] = []


# --------------------------------------------------------------------------
# Leads
# --------------------------------------------------------------------------

class LeadOut(ORMModel):
    id: int
    customer_id: int
    status: str
    score: int
    score_reasons: List[str] = []
    intent: List[str] = []
    budget: Optional[int] = None
    currency: str = "INR"
    clothing_categories: List[str] = []
    brands: List[str] = []
    size: Optional[str] = None
    timeline: Optional[str] = None
    location: Optional[str] = None
    barriers: List[str] = []
    sentiment: str = "neutral"
    language: str = "english"
    last_interaction_at: Optional[datetime] = None
    customer_name: Optional[str] = None
    phone_number: Optional[str] = None
    do_not_call: bool = False
    next_callback: Optional[str] = None


class LeadDetail(LeadOut):
    memory: Dict[str, Any] = {}
    calls: List[CallOut] = []
    transcript: List[MessageOut] = []
    score_history: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    whatsapp_messages: List[Dict[str, Any]] = []
    callbacks: List[Dict[str, Any]] = []


class LeadPatch(BaseModel):
    status: Optional[str] = None
    score: Optional[int] = None
    budget: Optional[int] = None
    size: Optional[str] = None
    timeline: Optional[str] = None
    location: Optional[str] = None
    do_not_call: Optional[bool] = None
    notes: Optional[str] = None


# --------------------------------------------------------------------------
# WhatsApp / callbacks
# --------------------------------------------------------------------------

class WhatsAppSendRequest(BaseModel):
    phone_number: Optional[str] = None
    lead_id: Optional[int] = None
    call_id: Optional[int] = None
    body: Optional[str] = None
    use_template: bool = True


class CallbackCreate(BaseModel):
    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    phone_number: Optional[str] = None
    when_text: str = Field(min_length=1, max_length=200)
    notes: Optional[str] = None


class CallbackOut(BaseModel):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    phone_number: Optional[str] = None
    lead_id: Optional[int] = None
    call_id: Optional[int] = None
    original_text: Optional[str] = None
    scheduled_time_utc: datetime
    scheduled_time_ist: str
    human_time: str
    confidence: float
    interpretation: Optional[str] = None
    status: str


class ParseTimeRequest(BaseModel):
    text: str


# --------------------------------------------------------------------------
# Config / training
# --------------------------------------------------------------------------

class StoreConfigPatch(BaseModel):
    profile: Optional[Dict[str, Any]] = None
    scoring_weights: Optional[Dict[str, int]] = None
    thresholds: Optional[Dict[str, int]] = None
    faq: Optional[List[Dict[str, Any]]] = None


class GenerateDatasetRequest(BaseModel):
    samples_per_label: int = Field(default=180, ge=30, le=2000)
    seed: int = 42


class TrainRequest(BaseModel):
    model_type: str = "tfidf_logreg"
    test_size: float = Field(default=0.2, ge=0.05, le=0.5)


class ClassifyRequest(BaseModel):
    text: str

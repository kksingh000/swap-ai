"""Runtime configuration: store profile, scoring weights, FAQ, provider switching."""
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.api import StoreConfigPatch
from app.services import config_service
from app.services.llm.factory import build_provider as build_llm, get_llm, set_llm
from app.services.telephony.factory import build_provider as build_telephony, set_telephony
from app.services.whatsapp.factory import build_provider as build_whatsapp, set_whatsapp

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/store")
async def get_store_config(db: Session = Depends(get_db)) -> Dict[str, Any]:
    config = config_service.get_config(db)
    return {
        "profile": config.profile,
        "scoring_weights": config.scoring_weights,
        "thresholds": config.thresholds,
        "faq": config.faq,
    }


@router.patch("/store")
async def patch_store_config(
    payload: StoreConfigPatch, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    config = config_service.get_config(db)
    if payload.profile is not None:
        config.profile = {**(config.profile or {}), **payload.profile}
    if payload.scoring_weights is not None:
        config.scoring_weights = {**(config.scoring_weights or {}), **payload.scoring_weights}
    if payload.thresholds is not None:
        config.thresholds = {**(config.thresholds or {}), **payload.thresholds}
    if payload.faq is not None:
        config.faq = payload.faq
    db.commit()
    db.refresh(config)
    return {
        "profile": config.profile,
        "scoring_weights": config.scoring_weights,
        "thresholds": config.thresholds,
        "faq": config.faq,
    }


@router.get("/providers")
async def get_providers() -> Dict[str, Any]:
    return {
        "llm": {
            "active": get_llm().name,
            "options": ["auto", "rules", "ollama", "huggingface", "openai_compatible"],
            "configured": {
                "ollama": settings.OLLAMA_BASE_URL,
                "huggingface": bool(settings.HF_API_TOKEN),
                "openai_compatible": bool(settings.OPENAI_API_KEY),
            },
        },
        "telephony": {"active": settings.TELEPHONY_PROVIDER, "options": ["mock", "twilio"]},
        "whatsapp": {"active": settings.WHATSAPP_PROVIDER, "options": ["mock", "twilio"]},
        "speech": {"stt": settings.STT_PROVIDER, "tts": settings.TTS_PROVIDER},
    }


@router.post("/providers")
async def switch_provider(payload: Dict[str, str] = Body(...)) -> Dict[str, Any]:
    """Hot-swap a provider without a restart. Credentials still come from env."""
    changed: Dict[str, str] = {}

    if "llm" in payload:
        set_llm(build_llm(payload["llm"]))
        changed["llm"] = get_llm().name
    if "telephony" in payload:
        provider = build_telephony(payload["telephony"])
        set_telephony(provider)
        changed["telephony"] = provider.name
    if "whatsapp" in payload:
        provider = build_whatsapp(payload["whatsapp"])
        set_whatsapp(provider)
        changed["whatsapp"] = provider.name

    if not changed:
        raise HTTPException(status_code=400, detail="Nothing to change")
    return {"changed": changed}

"""Runtime configuration: store profile, scoring weights, FAQ, provider switching."""
from typing import Any, Dict

import httpx
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


@router.get("/twilio-check")
async def twilio_check() -> Dict[str, Any]:
    """Validate the Twilio setup against Twilio itself.

    Separates the three things that all surface as one failed call: bad
    credentials, a from-number the account does not own, and a trial account
    refusing an unverified destination.
    """
    from app.services.twilio_auth import (
        twilio_auth,
        twilio_configured,
        twilio_credential_style,
    )

    style = twilio_credential_style()
    result: Dict[str, Any] = {
        "credential_style": style,
        "account_sid_set": bool(settings.TWILIO_ACCOUNT_SID),
        "account_sid_prefix": settings.TWILIO_ACCOUNT_SID[:6] or None,
        "from_number": settings.TWILIO_PHONE_NUMBER or None,
    }

    if not twilio_configured():
        result.update(
            ok=False,
            stage="credentials",
            problem="Twilio credentials are incomplete.",
            fix="Set TWILIO_ACCOUNT_SID plus either TWILIO_AUTH_TOKEN, or both "
            "TWILIO_API_KEY_SID and TWILIO_API_KEY_SECRET.",
        )
        return result

    auth = twilio_auth()
    base = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}"

    # 1. Do the credentials authenticate at all?
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{base}.json", auth=auth)
    except Exception as exc:  # noqa: BLE001
        result.update(ok=False, stage="network", problem=str(exc)[:200])
        return result

    if resp.status_code >= 400:
        payload = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        message = payload.get("message", resp.text[:200])
        fix = (
            "The API key secret is shown only once at creation - if it was not saved, "
            "create a new Standard API key, or switch to TWILIO_AUTH_TOKEN which is "
            "always visible in the Twilio console."
            if style == "api_key"
            else "Re-copy the Auth Token from the Twilio console dashboard."
        )
        result.update(
            ok=False,
            stage="authentication",
            http_status=resp.status_code,
            problem=message,
            fix=fix,
            note="Also confirm the credentials belong to this exact Account SID.",
        )
        return result

    account = resp.json()
    account_type = account.get("type")
    result.update(
        authenticated=True,
        account_status=account.get("status"),
        account_type=account_type,
        account_name=account.get("friendly_name"),
    )

    # 2. Does this account actually own the from-number, with voice enabled?
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            numbers = await client.get(
                f"{base}/IncomingPhoneNumbers.json", auth=auth, params={"PageSize": 50}
            )
        owned = [n for n in numbers.json().get("incoming_phone_numbers", [])]
        match = next(
            (n for n in owned if n.get("phone_number") == settings.TWILIO_PHONE_NUMBER), None
        )
        result["owned_numbers"] = [n.get("phone_number") for n in owned]
        if match is None:
            result.update(
                ok=False,
                stage="from_number",
                problem=f"{settings.TWILIO_PHONE_NUMBER} is not a number on this account.",
                fix="Set TWILIO_PHONE_NUMBER to one of owned_numbers.",
            )
            return result
        if not match.get("capabilities", {}).get("voice"):
            result.update(
                ok=False,
                stage="from_number",
                problem="That number has no voice capability.",
                fix="Buy a voice-capable number.",
            )
            return result
    except Exception as exc:  # noqa: BLE001
        result["number_check_error"] = str(exc)[:200]

    result["ok"] = True
    result["stage"] = "ready"
    if (account_type or "").lower() == "trial":
        result["trial_warning"] = (
            "This is a TRIAL account: it can only dial numbers added under "
            "Phone Numbers > Verified Caller IDs. Unverified destinations fail "
            "with error 21219."
        )
    return result


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

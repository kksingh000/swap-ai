"""Loads/creates the single store-configuration row."""
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.store_profile import (
    DEFAULT_FAQ,
    DEFAULT_SCORING_WEIGHTS,
    DEFAULT_STORE_PROFILE,
    DEFAULT_THRESHOLDS,
)
from app.models import StoreConfiguration


def get_config(db: Session) -> StoreConfiguration:
    config = db.query(StoreConfiguration).first()
    if config is None:
        config = StoreConfiguration(
            profile=dict(DEFAULT_STORE_PROFILE),
            scoring_weights=dict(DEFAULT_SCORING_WEIGHTS),
            thresholds=dict(DEFAULT_THRESHOLDS),
            faq=list(DEFAULT_FAQ),
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def get_profile(db: Session) -> Dict[str, Any]:
    return {**DEFAULT_STORE_PROFILE, **(get_config(db).profile or {})}


def get_weights(db: Session) -> Dict[str, int]:
    return {**DEFAULT_SCORING_WEIGHTS, **(get_config(db).scoring_weights or {})}


def get_thresholds(db: Session) -> Dict[str, int]:
    return {**DEFAULT_THRESHOLDS, **(get_config(db).thresholds or {})}


def get_faq(db: Session) -> list:
    return get_config(db).faq or list(DEFAULT_FAQ)

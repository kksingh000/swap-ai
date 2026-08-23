"""Trained lead-intent classifier (scikit-learn, ~200KB, CPU, instant).

Optional by design: if the artifact is missing the ensemble simply drops this
voter. Train it with `python training/train_classifier.py`.
"""
import os
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class LeadClassifier:
    def __init__(self, model_path: Optional[str] = None) -> None:
        # Resolved against the repo layout, not the working directory, so the
        # artifact is found whether you run from /backend, /training or root.
        from app.services.classification.trainer import _paths

        self.model_path = model_path or settings.CLASSIFIER_MODEL_PATH or ""
        if not os.path.isabs(self.model_path):
            default = _paths()["model"]
            self.model_path = default if not os.path.exists(self.model_path) else self.model_path
        self._pipeline = None
        self._meta: Dict[str, Any] = {}
        self._load_attempted = False

    @property
    def loaded(self) -> bool:
        self._ensure_loaded()
        return self._pipeline is not None

    def _ensure_loaded(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True

        path = os.path.abspath(self.model_path)
        if not os.path.exists(path):
            log.info("Lead classifier not found at %s (ensemble will use rules + LLM)", path)
            return
        try:
            import joblib  # imported lazily so the app runs without scikit-learn

            bundle = joblib.load(path)
            self._pipeline = bundle["pipeline"]
            self._meta = bundle.get("meta", {})
            log.info(
                "Lead classifier loaded (%s, accuracy=%s)",
                self._meta.get("model", "?"),
                self._meta.get("accuracy", "?"),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not load lead classifier: %s", exc)
            self._pipeline = None

    def predict(self, text: str) -> Optional[Tuple[str, float]]:
        self._ensure_loaded()
        if self._pipeline is None or not (text or "").strip():
            return None
        try:
            label = self._pipeline.predict([text])[0]
            confidence = 0.5
            if hasattr(self._pipeline, "predict_proba"):
                proba = self._pipeline.predict_proba([text])[0]
                confidence = float(max(proba))
            return str(label), round(confidence, 3)
        except Exception as exc:  # noqa: BLE001
            log.warning("Classifier inference failed: %s", exc)
            return None

    def info(self) -> Dict[str, Any]:
        self._ensure_loaded()
        return {
            "loaded": self._pipeline is not None,
            "path": os.path.abspath(self.model_path),
            **self._meta,
        }

    def reload(self) -> None:
        self._load_attempted = False
        self._pipeline = None
        self._ensure_loaded()


_classifier: Optional[LeadClassifier] = None


def get_classifier() -> LeadClassifier:
    global _classifier
    if _classifier is None:
        _classifier = LeadClassifier()
    return _classifier

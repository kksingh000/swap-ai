"""Dataset generation, classifier training and method comparison."""
import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.schemas.api import ClassifyRequest, GenerateDatasetRequest, TrainRequest
from app.schemas.nlu import CustomerMemory
from app.services.classification import trainer
from app.services.classification.ml_classifier import get_classifier
from app.services.classification.scoring import score_lead
from app.services.conversation.rules_nlu import extract_turn
from app.services.llm.factory import get_llm

log = get_logger(__name__)
router = APIRouter(prefix="/training", tags=["training"])


@router.post("/generate-dataset")
async def generate_dataset(payload: GenerateDatasetRequest) -> Dict[str, Any]:
    result = await asyncio.to_thread(
        trainer.write_dataset, payload.samples_per_label, payload.seed
    )
    return result


@router.post("/train")
async def train_model(payload: TrainRequest) -> Dict[str, Any]:
    try:
        metrics = await asyncio.to_thread(trainer.train, payload.test_size, 42, payload.model_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    get_classifier().reload()
    return metrics


@router.get("/results")
async def training_results() -> Dict[str, Any]:
    metrics = trainer.load_metrics()
    return {
        "trained": metrics is not None,
        "metrics": metrics,
        "classifier": get_classifier().info(),
        "dataset_rows": len(trainer.load_dataset()),
    }


@router.get("/dataset")
async def peek_dataset(limit: int = 25) -> Dict[str, Any]:
    rows = trainer.load_dataset()
    return {"total": len(rows), "rows": rows[:limit]}


@router.post("/classify")
async def classify_text(payload: ClassifyRequest) -> Dict[str, Any]:
    """Compare all three classification methods on one utterance."""
    turn = extract_turn(payload.text)
    memory = CustomerMemory().merge_turn(turn)
    rules = score_lead(memory, [turn])
    prediction = get_classifier().predict(payload.text)

    llm_result = None
    llm = get_llm()
    if llm.available:
        from app.services.classification.ensemble import _llm_classify

        llm_result = await _llm_classify(llm, [{"role": "customer", "content": payload.text}])

    return {
        "utterance": payload.text,
        "extracted": turn.model_dump(mode="json"),
        "methods": {
            "rules": {
                "label": rules.classification,
                "score": rules.score,
                "reasons": rules.reasons,
            },
            "classifier": (
                {"label": prediction[0], "confidence": prediction[1]} if prediction else None
            ),
            "llm": llm_result,
        },
    }


@router.post("/benchmark")
async def benchmark() -> Dict[str, Any]:
    """Run rules vs classifier over a held-out slice and report agreement."""
    rows: List[Dict[str, str]] = trainer.load_dataset()
    if not rows:
        raise HTTPException(status_code=404, detail="No dataset found. Generate one first.")

    sample = rows[:200]
    classifier = get_classifier()
    rules_correct = ml_correct = agree = 0
    ml_available = classifier.loaded

    for row in sample:
        turn = extract_turn(row["utterance"])
        memory = CustomerMemory().merge_turn(turn)
        rules_label = score_lead(memory, [turn]).classification
        if rules_label == row["label"]:
            rules_correct += 1

        if ml_available:
            prediction = classifier.predict(row["utterance"])
            if prediction:
                if prediction[0] == row["label"]:
                    ml_correct += 1
                if prediction[0] == rules_label:
                    agree += 1

    total = len(sample)
    return {
        "sample_size": total,
        "rules_accuracy": round(rules_correct / total, 3),
        "classifier_accuracy": round(ml_correct / total, 3) if ml_available else None,
        "agreement": round(agree / total, 3) if ml_available else None,
        "note": "Rules are tuned for business explainability; the classifier catches phrasing rules miss. The ensemble uses both.",
    }

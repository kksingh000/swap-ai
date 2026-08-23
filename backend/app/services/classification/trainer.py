"""Trains the lead classifier.

Model choice: TF-IDF over **word + character n-grams** feeding a linear model.
Character n-grams are the important part - Hinglish has no fixed spelling
("nahi/nahin/nai", "chahiye/chaiye"), and char n-grams absorb that variation
without any embedding download. The whole artifact is a few hundred KB and
inference is sub-millisecond on CPU.

Optional upgrade path (documented in the README): sentence-transformer
embeddings + logistic regression, or a fine-tuned MuRIL/IndicBERT.
"""
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.services.classification.dataset import dataset_stats, generate_dataset

log = get_logger(__name__)

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "training", "artifacts")
DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "training", "dataset")


def _paths() -> Dict[str, str]:
    return {
        "artifact_dir": os.path.abspath(ARTIFACT_DIR),
        "dataset_dir": os.path.abspath(DATASET_DIR),
        "model": os.path.abspath(os.path.join(ARTIFACT_DIR, "lead_classifier.joblib")),
        "metrics": os.path.abspath(os.path.join(ARTIFACT_DIR, "metrics.json")),
        "dataset": os.path.abspath(os.path.join(DATASET_DIR, "leads.jsonl")),
    }


def write_dataset(samples_per_label: int = 180, seed: int = 42) -> Dict[str, Any]:
    paths = _paths()
    os.makedirs(paths["dataset_dir"], exist_ok=True)

    rows = generate_dataset(samples_per_label=samples_per_label, seed=seed)
    with open(paths["dataset"], "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    stats = dataset_stats(rows)
    log.info("Dataset written: %s rows -> %s", len(rows), paths["dataset"])
    return {"path": paths["dataset"], "rows": len(rows), "stats": stats, "sample": rows[:8]}


def load_dataset(path: Optional[str] = None) -> List[Dict[str, str]]:
    path = path or _paths()["dataset"]
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def train(test_size: float = 0.2, seed: int = 42, model_type: str = "tfidf_logreg") -> Dict[str, Any]:
    try:
        import joblib
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import classification_report, confusion_matrix
        from sklearn.model_selection import GroupShuffleSplit, cross_val_score, train_test_split
        from sklearn.pipeline import Pipeline, FeatureUnion
        from sklearn.svm import LinearSVC
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "scikit-learn and joblib are required to train. Install with: pip install scikit-learn joblib"
        ) from exc

    paths = _paths()
    rows = load_dataset()
    if not rows:
        write_dataset()
        rows = load_dataset()

    texts = [r["utterance"] for r in rows]
    labels = [r["label"] for r in rows]
    groups = [r.get("template_id") for r in rows]

    # Honest evaluation: hold out *whole templates*, so the test set contains
    # phrasings the model has never seen. A random row split would leak
    # near-duplicate sentences into the test set and report ~100% accuracy.
    if all(groups):
        splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
        train_idx, test_idx = next(splitter.split(texts, labels, groups))
        x_train = [texts[i] for i in train_idx]
        x_test = [texts[i] for i in test_idx]
        y_train = [labels[i] for i in train_idx]
        y_test = [labels[i] for i in test_idx]
        split_strategy = "grouped_by_template (unseen phrasings)"
    else:
        x_train, x_test, y_train, y_test = train_test_split(
            texts, labels, test_size=test_size, random_state=seed, stratify=labels
        )
        split_strategy = "random_row_split"

    features = FeatureUnion(
        [
            ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=1)),
        ]
    )
    classifier = (
        LinearSVC(C=1.0)
        if model_type == "tfidf_svm"
        else LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced")
    )
    pipeline = Pipeline([("features", features), ("clf", classifier)])
    pipeline.fit(x_train, y_train)

    predictions = pipeline.predict(x_test)
    report = classification_report(y_test, predictions, output_dict=True, zero_division=0)
    matrix = confusion_matrix(y_test, predictions, labels=["HOT", "WARM", "COLD"]).tolist()
    cv_scores = cross_val_score(pipeline, texts, labels, cv=5)

    os.makedirs(paths["artifact_dir"], exist_ok=True)
    meta = {
        "model": model_type,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "accuracy": round(float(report["accuracy"]), 4),
        "cv_mean_accuracy": round(float(cv_scores.mean()), 4),
        "cv_std": round(float(cv_scores.std()), 4),
        "split_strategy": split_strategy,
        "labels": ["HOT", "WARM", "COLD"],
    }
    joblib.dump({"pipeline": pipeline, "meta": meta}, paths["model"])

    metrics = {
        **meta,
        "classification_report": report,
        "confusion_matrix": {"labels": ["HOT", "WARM", "COLD"], "matrix": matrix},
        "dataset_stats": dataset_stats(rows),
        "artifact": paths["model"],
    }
    with open(paths["metrics"], "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2, ensure_ascii=False)

    log.info(
        "Classifier trained: accuracy=%.3f cv=%.3f (+/-%.3f) -> %s",
        meta["accuracy"], meta["cv_mean_accuracy"], meta["cv_std"], paths["model"],
    )
    return metrics


def load_metrics() -> Optional[Dict[str, Any]]:
    path = _paths()["metrics"]
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)

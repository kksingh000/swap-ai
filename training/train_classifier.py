"""Train the lead classifier.

    python training/train_classifier.py --model tfidf_logreg

Saves training/artifacts/lead_classifier.joblib + metrics.json. The backend
picks the artifact up automatically on the next request.
"""
import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app.services.classification import trainer  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the lead classifier")
    parser.add_argument("--model", default="tfidf_logreg", choices=["tfidf_logreg", "tfidf_svm"])
    parser.add_argument("--test-size", type=float, default=0.2)
    args = parser.parse_args()

    if not trainer.load_dataset():
        print("No dataset found - generating one first...")
        trainer.write_dataset()

    metrics = trainer.train(test_size=args.test_size, model_type=args.model)

    print("\n" + "=" * 62)
    print(f"  Model:            {metrics['model']}")
    print(f"  Training rows:    {metrics['rows']}")
    print(f"  Holdout accuracy: {metrics['accuracy']:.3f}")
    print(f"  5-fold CV:        {metrics['cv_mean_accuracy']:.3f} +/- {metrics['cv_std']:.3f}")
    print("=" * 62)

    report = metrics["classification_report"]
    print(f"\n  {'label':6} {'precision':>10} {'recall':>8} {'f1':>8} {'support':>8}")
    for label in ("HOT", "WARM", "COLD"):
        row = report.get(label)
        if row:
            print(
                f"  {label:6} {row['precision']:>10.3f} {row['recall']:>8.3f} "
                f"{row['f1-score']:>8.3f} {int(row['support']):>8}"
            )

    matrix = metrics["confusion_matrix"]
    print("\n  Confusion matrix (rows = true, cols = predicted)")
    print("           " + "".join(f"{label:>7}" for label in matrix["labels"]))
    for label, row in zip(matrix["labels"], matrix["matrix"]):
        print(f"  {label:>7}  " + "".join(f"{value:>7}" for value in row))

    print(f"\n  Artifact: {metrics['artifact']}\n")


if __name__ == "__main__":
    main()

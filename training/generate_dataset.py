"""Generate the synthetic lead-classification dataset.

    python training/generate_dataset.py --samples 180

Writes training/dataset/leads.jsonl with English / Hindi / Hinglish utterances
labelled HOT, WARM or COLD.
"""
import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app.services.classification import trainer  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate lead-classification data")
    parser.add_argument("--samples", type=int, default=180, help="samples per label")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = trainer.write_dataset(samples_per_label=args.samples, seed=args.seed)

    print(f"\nWrote {result['rows']} rows -> {result['path']}\n")
    print("By label:    ", result["stats"]["by_label"])
    print("By language: ", result["stats"]["by_language"])
    print("\nSamples:")
    for row in result["sample"]:
        print(f"  [{row['label']:4}] ({row['language']:8}) {row['utterance']}")


if __name__ == "__main__":
    main()

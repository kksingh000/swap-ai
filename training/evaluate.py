"""Compare the classification methods on held-out and hand-written cases.

    python training/evaluate.py

Prints rules vs trained-classifier accuracy and the cases where they disagree -
which is exactly where the ensemble earns its keep.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app.schemas.nlu import CustomerMemory  # noqa: E402
from app.services.classification import trainer  # noqa: E402
from app.services.classification.ml_classifier import get_classifier  # noqa: E402
from app.services.classification.scoring import score_lead  # noqa: E402
from app.services.conversation.rules_nlu import extract_turn  # noqa: E402

HAND_WRITTEN = [
    ("Mujhe branded jackets chahiye 1500 tak, is hafte chahiye", "HOT"),
    ("Send me the catalog on WhatsApp please", "HOT"),
    ("I'll think about it and let you know next month", "WARM"),
    ("Kal shaam call karna, abhi busy hoon", "WARM"),
    ("Bas dekh raha tha, kuch lena nahi hai", "COLD"),
    ("Please remove my number, don't call again", "COLD"),
    ("How much do you pay if I sell my Levis jeans?", "HOT"),
    ("Achha idea hai par pehle wardrobe check karungi", "WARM"),
]

NOTE = (
    "\n  Note: the rules engine scores a WHOLE CONVERSATION and deliberately returns"
    "\n  UNKNOWN for a single ambiguous line, while the classifier scores individual"
    "\n  utterances. That difference is exactly why the ensemble combines them"
    "\n  instead of relying on either one alone."
)


def rules_label(text: str) -> str:
    turn = extract_turn(text)
    memory = CustomerMemory().merge_turn(turn)
    return score_lead(memory, [turn]).classification


def main() -> None:
    classifier = get_classifier()
    rows = trainer.load_dataset()

    if not rows:
        print("No dataset found. Run: python training/generate_dataset.py")
        return

    sample = rows[:300]
    rules_hits = ml_hits = agreements = undecided = 0
    disagreements = []

    for row in sample:
        truth, text = row["label"], row["utterance"]
        rule = rules_label(text)
        rules_hits += rule == truth
        undecided += rule == "UNKNOWN"

        prediction = classifier.predict(text)
        if prediction:
            ml_hits += prediction[0] == truth
            agreements += prediction[0] == rule
            if prediction[0] != rule and len(disagreements) < 10:
                disagreements.append((text, truth, rule, prediction[0], prediction[1]))

    total = len(sample)
    decided = total - undecided

    print("=" * 72)
    print(f"Evaluated on {total} single utterances")
    print("=" * 72)
    print(f"  Rules engine accuracy:        {rules_hits / total:.3f}")
    print(
        f"    ...among lines it decided:  {(rules_hits / decided) if decided else 0:.3f}"
        f"   ({undecided} returned UNKNOWN)"
    )
    if classifier.loaded:
        print(f"  Trained classifier accuracy:  {ml_hits / total:.3f}")
        print(f"  Agreement between them:       {agreements / total:.3f}")
        print("  (this slice overlaps the training rows - the honest number is the")
        print("   grouped-by-template holdout reported by train_classifier.py)")
    else:
        print("  Trained classifier:           not available (run train_classifier.py)")
    print(NOTE)

    if disagreements:
        print("\nWhere they disagree (this is what the ensemble resolves):")
        for text, truth, rule, ml, confidence in disagreements:
            print(f"  truth={truth:4} rules={rule:7} clf={ml:4} ({confidence:.2f})  {text[:58]}")

    print("\n" + "=" * 72)
    print("Hand-written cases")
    print("=" * 72)
    print(f"  {'expected':9} {'rules':8} {'classifier':13} utterance")
    for text, expected in HAND_WRITTEN:
        prediction = classifier.predict(text)
        ml = f"{prediction[0]} ({prediction[1]:.2f})" if prediction else "n/a"
        print(f"  {expected:9} {rules_label(text):8} {ml:13} {text[:52]}")


if __name__ == "__main__":
    main()

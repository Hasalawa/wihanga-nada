"""Check which of our seed endemics BirdNET can actually detect.

BirdNET 2.4 does not know every Sri Lankan endemic. This compares
wihanga/endemics.json against the model's label file, prints the gaps, and
exits non-zero if any `in_birdnet` flag in the JSON is wrong.

    python tools/check_coverage.py
    python tools/check_coverage.py --labels path/to/BirdNET_GLOBAL_6K_V2.4_Labels.txt
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABELS_REL = Path("models/analyzer/BirdNET_GLOBAL_6K_V2.4_Labels.txt")


def default_labels() -> Path | None:
    spec = importlib.util.find_spec("birdnetlib")  # find without importing (importing is heavy)
    if spec and spec.submodule_search_locations:
        return Path(list(spec.submodule_search_locations)[0]) / LABELS_REL
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, default=default_labels())
    args = ap.parse_args()
    if not args.labels or not args.labels.exists():
        print("Labels file not found. Install birdnetlib or pass --labels.", file=sys.stderr)
        return 2

    known = {line.split("_")[0].strip().lower() for line in args.labels.read_text(encoding="utf-8").splitlines() if line}
    birds = json.loads((ROOT / "wihanga" / "endemics.json").read_text(encoding="utf-8"))

    covered, missing, wrong = [], [], []
    for b in birds:
        present = b["scientific_name"].lower() in known
        (covered if present else missing).append(b)
        if present != b["in_birdnet"]:
            wrong.append(b)

    print(f"BirdNET 2.4 covers {len(covered)} of {len(birds)} endemics in the seed list.\n")
    print("NOT covered (candidates for a custom classifier):")
    for b in missing:
        print(f"  - {b['common_name']} ({b['scientific_name']}) [{b['zone']}]")
    if wrong:
        print("\nWrong in_birdnet flag in endemics.json:")
        for b in wrong:
            print(f"  ! {b['scientific_name']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

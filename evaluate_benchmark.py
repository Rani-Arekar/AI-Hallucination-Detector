import argparse
import json
from pathlib import Path

from app.evaluation import compare_predictions, evaluate_predictions


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate precomputed factuality predictions.")
    parser.add_argument("dataset", type=Path, help="Labeled prediction JSONL file")
    parser.add_argument("--split", default="test", help="Dataset split to score (default: test)")
    parser.add_argument("--output", type=Path, help="Optional path for the JSON report")
    parser.add_argument("--compare", action="store_true", help="Compare baseline and improved prediction fields")
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in args.dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = [row for row in rows if row.get("split") == args.split]
    if not selected:
        parser.error(f"no rows found for split {args.split!r}")

    report = (
        compare_predictions(selected)
        if args.compare
        else evaluate_predictions(selected)
    )
    output = json.dumps({"split": args.split, "report": report}, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
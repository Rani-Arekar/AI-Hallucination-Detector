import argparse
import json
from pathlib import Path

from app.evaluation import normalize_fever_record


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize a locally downloaded, labeled FEVER JSONL split."
    )
    parser.add_argument("input", type=Path, help="Path to the licensed local FEVER JSONL file")
    parser.add_argument("output", type=Path, help="Destination normalized JSONL file")
    parser.add_argument("--split", required=True, choices=("train", "validation", "test"))
    args = parser.parse_args()

    source_rows = [
        json.loads(line)
        for line in args.input.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    normalized = [normalize_fever_record(row, args.split) for row in source_rows]
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in normalized),
        encoding="utf-8",
    )
    print(f"Normalized {len(normalized)} labeled FEVER rows into {args.output}")


if __name__ == "__main__":
    main()
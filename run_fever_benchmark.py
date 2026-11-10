import argparse
import asyncio
import json
import time
from pathlib import Path

from app.detector.fact_check import fact_check_claims
from app.detector.scoring import score_claim

VERDICT_MAP = {
    "SUPPORTED": "SUPPORTED",
    "PARTIALLY_SUPPORTED": "UNCERTAIN",
    "CONTRADICTED": "CONTRADICTED",
    "UNCERTAIN": "UNCERTAIN",
    "NO_RELEVANT_EVIDENCE": "UNVERIFIABLE",
    "INSUFFICIENT_EVIDENCE": "UNVERIFIABLE",
}


async def predict_records(
    rows: list[dict], evidence_source: str, limit: int
) -> list[dict]:
    if limit < 1:
        raise ValueError("limit must be at least one")
    selected = rows[:limit]
    results = []
    for row in selected:
        started = time.perf_counter()
        claim = row["text"]
        reports, _ = await fact_check_claims(
            [claim],
            max_concurrent=1,
            use_web_search=evidence_source in {"web", "both"},
            use_knowledge_base=evidence_source in {"knowledge-base", "both"},
            claim_contexts=[{"source_text": claim}],
        )
        report = reports[0]
        verdict = report["verdict"]
        scored = score_claim(report)
        results.append(
            {
                **row,
                "predicted": VERDICT_MAP.get(verdict, "UNCERTAIN"),
                "hallucination_risk_score": scored["hallucination_risk"],
                "retrieved_evidence": report.get("evidence_items", []),
                "processing_ms": round((time.perf_counter() - started) * 1000, 1),
                "provider_failed": (
                    report.get("evidence_availability") == "verification_unavailable"
                    or bool(report.get("error"))
                ),
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run bounded live verification on a locally prepared FEVER JSONL split."
    )
    parser.add_argument("input", type=Path, help="Normalized FEVER JSONL file")
    parser.add_argument("output", type=Path, help="Prediction JSONL destination")
    parser.add_argument("--limit", type=int, required=True, help="Maximum claims to process; each may call Gemini and web search")
    parser.add_argument(
        "--evidence-source",
        choices=("knowledge-base", "web", "both"),
        default="both",
    )
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for line in args.input.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    predictions = asyncio.run(
        predict_records(rows, args.evidence_source, args.limit)
    )
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions),
        encoding="utf-8",
    )
    print(f"Wrote {len(predictions)} predictions to {args.output}")


if __name__ == "__main__":
    main()
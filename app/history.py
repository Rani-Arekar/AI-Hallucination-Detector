from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select

from app.db import AnalysisRecord, db_session


def _status(risk: int) -> str:
    if risk >= 30:
        return "High Risk"
    if risk >= 15:
        return "Uncertain"
    if risk == 0:
        return "Reliable"
    return "Mostly Reliable"


def save_analysis(
    owner_id: str,
    text: str,
    response: dict[str, Any],
    mode: str,
    evidence_source: str,
    save_input_text: bool,
) -> None:
    counts = {
        "supported": sum(c["status"] == "supported" for c in response["claims"]),
        "contradicted": sum(c["status"] == "contradicted" for c in response["claims"]),
        "uncertain": sum(c["status"] == "uncertain" for c in response["claims"]),
        "unverifiable": sum(c["status"] == "unverifiable" for c in response["claims"]),
    }
    risk = response["hallucinationRiskScore"]
    saved_title = text.strip().splitlines()[0][:200] or "Untitled analysis"
    record = AnalysisRecord(
        id=response["analysisId"],
        owner_id=owner_id,
        title=saved_title if save_input_text else "Saved analysis",
        original_input=text if save_input_text else None,
        preview=text.strip()[:300] if save_input_text else "",
        reliability_score=response["reliabilityScore"],
        hallucination_risk_score=risk,
        decision_confidence=response["decisionConfidence"],
        total_claims=len(response["claims"]),
        supported_claims=counts["supported"],
        contradicted_claims=counts["contradicted"],
        uncertain_claims=counts["uncertain"],
        unverifiable_claims=counts["unverifiable"],
        status=_status(risk),
        source_type=evidence_source,
        verification_mode=mode,
        score_type=response["scoreType"],
        claims=response["claims"],
    )
    with db_session() as session:
        session.merge(record)
        session.commit()


def list_analyses(owner_id: str) -> list[AnalysisRecord]:
    with db_session() as session:
        return list(session.scalars(select(AnalysisRecord).where(AnalysisRecord.owner_id == owner_id).order_by(AnalysisRecord.created_at.desc())))


def get_analysis(owner_id: str, analysis_id: str) -> AnalysisRecord | None:
    with db_session() as session:
        return session.scalar(select(AnalysisRecord).where(AnalysisRecord.id == analysis_id, AnalysisRecord.owner_id == owner_id))


def delete_analyses(owner_id: str, ids: list[str]) -> None:
    with db_session() as session:
        session.execute(delete(AnalysisRecord).where(AnalysisRecord.owner_id == owner_id, AnalysisRecord.id.in_(ids)))
        session.commit()


def analytics(owner_id: str, days: int | None = None) -> dict[str, Any]:
    records = list_analyses(owner_id)
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        records = [r for r in records if r.created_at.replace(tzinfo=timezone.utc) >= cutoff]
    total = len(records)
    claims = sum(r.total_claims for r in records)
    avg = round(sum(r.reliability_score for r in records) / total, 1) if total else 0
    risk = round(sum(r.hallucination_risk_score for r in records) / total, 1) if total else 0
    breakdown = [
        {"name": "Supported", "value": sum(r.supported_claims for r in records), "color": "#2c9b6c"},
        {"name": "Uncertain", "value": sum(r.uncertain_claims for r in records), "color": "#d99524"},
        {"name": "Contradicted", "value": sum(r.contradicted_claims for r in records), "color": "#e34850"},
        {"name": "Unverifiable", "value": sum(r.unverifiable_claims for r in records), "color": "#8793a8"},
    ]
    trend = [
        {"date": r.created_at.isoformat(), "reliability": r.reliability_score, "analyses": 1}
        for r in reversed(records)
    ]
    return {"totalAnalyses": total, "averageReliability": avg, "hallucinationRate": risk, "claimsVerified": claims, "claimBreakdown": breakdown, "reliabilityTrend": trend, "records": records}

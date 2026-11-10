"""Offline metrics for labeled factuality predictions; never used in serving."""

from __future__ import annotations

from math import isfinite
from typing import Any

VERDICTS = (
    "SUPPORTED",
    "CONTRADICTED",
    "PARTIALLY_SUPPORTED",
    "UNCERTAIN",
    "UNVERIFIABLE",
)

FEVER_LABELS = {
    "SUPPORTS": "SUPPORTED",
    "REFUTES": "CONTRADICTED",
    "NOT ENOUGH INFO": "UNVERIFIABLE",
}


def normalize_fever_record(record: dict[str, Any], split: str) -> dict[str, Any]:
    """Normalize one labeled FEVER record; no FEVER data is bundled here."""
    label = str(record.get("label", "")).upper()
    if label not in FEVER_LABELS:
        raise ValueError(f"unsupported or missing FEVER label: {label!r}")
    claim = record.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("FEVER record must contain a non-empty claim")

    evidence_ids = set()
    for evidence_set in record.get("evidence", []):
        if not isinstance(evidence_set, list):
            continue
        for item in evidence_set:
            if (
                isinstance(item, list)
                and len(item) >= 4
                and isinstance(item[2], str)
                and isinstance(item[3], int)
            ):
                evidence_ids.add(f"{item[2]}:{item[3]}")

    return {
        "dataset": "FEVER",
        "id": record.get("id"),
        "split": split,
        "text": claim.strip(),
        "expected": FEVER_LABELS[label],
        "expected_evidence_ids": sorted(evidence_ids),
    }


def _safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _calibration_metrics(rows: list[dict[str, Any]], bins: int) -> dict | None:
    for row in rows:
        score = row.get("hallucination_risk_score")
        if score is not None and not 0 <= float(score) <= 100:
            raise ValueError("hallucination_risk_score must be between 0 and 100")
    samples = [
        (float(row["hallucination_risk_score"]) / 100, int(row["is_hallucination"]))
        for row in rows
        if row.get("hallucination_risk_score") is not None
        and row.get("is_hallucination") in (0, 1, False, True)
    ]
    if not samples:
        return None

    brier = sum((probability - label) ** 2 for probability, label in samples) / len(samples)
    curve = []
    expected_calibration_error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        selected = [
            (probability, label)
            for probability, label in samples
            if lower <= probability < upper or (index == bins - 1 and probability == 1)
        ]
        if not selected:
            continue
        mean_probability = sum(item[0] for item in selected) / len(selected)
        observed_rate = sum(item[1] for item in selected) / len(selected)
        expected_calibration_error += (
            len(selected) / len(samples) * abs(mean_probability - observed_rate)
        )
        curve.append(
            {
                "lower": lower,
                "upper": upper,
                "mean_probability": mean_probability,
                "observed_rate": observed_rate,
                "samples": len(selected),
            }
        )
    return {
        "interpretation": "diagnostic against labels; input scores are not validated probabilities",
        "brier_score": brier,
        "expected_calibration_error": expected_calibration_error,
        "reliability_curve": curve,
        "sample_count": len(samples),
    }


def _retrieval_metrics(rows: list[dict[str, Any]]) -> dict | None:
    rows_with_ids = [
        row
        for row in rows
        if isinstance(row.get("expected_evidence_ids"), list)
        and isinstance(row.get("retrieved_evidence_ids"), list)
    ]
    if not rows_with_ids:
        return None

    true_positive = false_positive = false_negative = 0
    for row in rows_with_ids:
        expected = set(row["expected_evidence_ids"])
        retrieved = set(row["retrieved_evidence_ids"])
        true_positive += len(expected & retrieved)
        false_positive += len(retrieved - expected)
        false_negative += len(expected - retrieved)
    return {
        "precision": _safe_divide(true_positive, true_positive + false_positive),
        "recall": _safe_divide(true_positive, true_positive + false_negative),
        "relevant_retrieved": true_positive,
        "irrelevant_retrieved": false_positive,
        "relevant_missed": false_negative,
        "sample_count": len(rows_with_ids),
    }


def evaluate_predictions(
    rows: list[dict[str, Any]], prediction_field: str = "predicted", bins: int = 10
) -> dict[str, Any]:
    if not rows:
        raise ValueError("evaluation rows must not be empty")
    if bins < 1:
        raise ValueError("bins must be positive")

    labels = list(VERDICTS)
    expected = [str(row["expected"]).upper() for row in rows]
    predicted = [str(row[prediction_field]).upper() for row in rows]
    if not set(expected + predicted).issubset(VERDICTS):
        raise ValueError(f"labels must be one of: {', '.join(VERDICTS)}")

    matrix = {label: {prediction: 0 for prediction in VERDICTS} for label in VERDICTS}
    for actual, prediction in zip(expected, predicted):
        matrix[actual][prediction] += 1

    per_class = {}
    f1_values = []
    for label in labels:
        true_positive = matrix[label][label]
        false_positive = sum(matrix[other][label] for other in VERDICTS if other != label)
        false_negative = sum(matrix[label][other] for other in VERDICTS if other != label)
        precision = _safe_divide(true_positive, true_positive + false_positive)
        recall = _safe_divide(true_positive, true_positive + false_negative)
        f1 = _safe_divide(2 * precision * recall, precision + recall)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(matrix[label].values()),
        }
        f1_values.append(f1)

    actual_positive = [label == "CONTRADICTED" for label in expected]
    predicted_positive = [label == "CONTRADICTED" for label in predicted]
    false_positive = sum(not actual and predicted for actual, predicted in zip(actual_positive, predicted_positive))
    false_negative = sum(actual and not predicted for actual, predicted in zip(actual_positive, predicted_positive))
    true_negative = sum(not actual and not predicted for actual, predicted in zip(actual_positive, predicted_positive))
    true_positive = sum(actual and predicted for actual, predicted in zip(actual_positive, predicted_positive))
    processing_times = [
        float(row["processing_ms"])
        for row in rows
        if isinstance(row.get("processing_ms"), (int, float))
        and not isinstance(row.get("processing_ms"), bool)
        and isfinite(float(row["processing_ms"]))
        and row["processing_ms"] >= 0
    ]
    provider_rows = [row for row in rows if isinstance(row.get("provider_failed"), bool)]

    return {
        "sample_count": len(rows),
        "prediction_field": prediction_field,
        "accuracy": sum(actual == prediction for actual, prediction in zip(expected, predicted)) / len(rows),
        "macro_f1": sum(f1_values) / len(f1_values),
        "per_class": per_class,
        "confusion_matrix": matrix,
        "contradicted_false_positive_rate": _safe_divide(false_positive, false_positive + true_negative),
        "contradicted_false_negative_rate": _safe_divide(false_negative, false_negative + true_positive),
        "calibration": _calibration_metrics(rows, bins),
        "evidence_retrieval": _retrieval_metrics(rows),
        "mean_processing_ms": (
            sum(processing_times) / len(processing_times) if processing_times else None
        ),
        "processing_time_sample_count": len(processing_times),
        "provider_failure_rate": (
            sum(row["provider_failed"] for row in provider_rows) / len(provider_rows)
            if provider_rows
            else None
        ),
        "provider_failure_sample_count": len(provider_rows),
    }


def compare_predictions(
    rows: list[dict[str, Any]], baseline_field: str = "baseline_predicted", improved_field: str = "improved_predicted"
) -> dict[str, Any]:
    return {
        "baseline": evaluate_predictions(rows, baseline_field),
        "improved": evaluate_predictions(rows, improved_field),
    }
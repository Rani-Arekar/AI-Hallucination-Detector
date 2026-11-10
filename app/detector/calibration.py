"""Optional empirical calibration for future labeled-data evaluation.

This module is intentionally not used by the live heuristic pipeline. It
calibrates a score only when supplied with a held-out dataset containing
labels where 1 means hallucinated and 0 means not hallucinated.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    observed_rate: float
    samples: int


def fit_empirical_bins(
    scores: list[float], labels: list[int], bins: int = 10
) -> list[CalibrationBin]:
    """Fit non-parametric empirical rates on a held-out labeled dataset."""
    if len(scores) != len(labels) or not scores:
        raise ValueError("scores and labels must be non-empty and the same length")
    if bins < 1:
        raise ValueError("bins must be positive")
    if any(not 0 <= score <= 100 for score in scores):
        raise ValueError("scores must be between 0 and 100")
    if any(label not in (0, 1) for label in labels):
        raise ValueError("labels must be 0 or 1")

    result = []
    for index in range(bins):
        lower = index * 100 / bins
        upper = (index + 1) * 100 / bins
        selected = [
            label
            for score, label in zip(scores, labels)
            if lower <= score < upper or (index == bins - 1 and score == 100)
        ]
        if selected:
            result.append(
                CalibrationBin(
                    lower=lower,
                    upper=upper,
                    observed_rate=sum(selected) / len(selected),
                    samples=len(selected),
                )
            )
    if not result:
        raise ValueError("held-out data did not contain any usable bins")
    return result


def calibrate_score(score: float, table: list[CalibrationBin]) -> float:
    """Return the observed hallucination rate for a fitted score bin."""
    if not 0 <= score <= 100:
        raise ValueError("score must be between 0 and 100")
    for item in table:
        if item.lower <= score < item.upper or (
            score == 100 and item.upper == 100
        ):
            return item.observed_rate
    nearest = min(table, key=lambda item: min(abs(score - item.lower), abs(score - item.upper)))
    return nearest.observed_rate

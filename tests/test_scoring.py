import pytest

from app.detector.scoring import DEFAULT_WEIGHTS, compute_final_score


def test_perfect_scores_give_zero_risk():
    scores = {"fact": 1.0, "logic": 1.0, "citation": 1.0, "confidence": 1.0, "cross": 1.0}
    assert compute_final_score(scores) == 0


def test_worst_scores_give_max_risk():
    scores = {"fact": 0.0, "logic": 0.0, "citation": 0.0, "confidence": 0.0, "cross": 0.0}
    assert compute_final_score(scores) == 100


def test_default_weights_sum_to_one():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_missing_score_key_raises():
    scores = {"fact": 1.0, "logic": 1.0, "citation": 1.0, "confidence": 1.0}  # missing "cross"
    with pytest.raises(ValueError):
        compute_final_score(scores)


def test_custom_weights_not_summing_to_one_raises():
    scores = {"fact": 1.0, "logic": 1.0, "citation": 1.0, "confidence": 1.0, "cross": 1.0}
    bad_weights = {"fact": 0.5, "logic": 0.5, "citation": 0.5, "confidence": 0.5, "cross": 0.5}
    with pytest.raises(ValueError):
        compute_final_score(scores, weights=bad_weights)


def test_risk_score_is_always_clamped_0_to_100():
    scores = {"fact": 1.0, "logic": 1.0, "citation": 1.0, "confidence": 1.0, "cross": 1.0}
    risk = compute_final_score(scores)
    assert 0 <= risk <= 100

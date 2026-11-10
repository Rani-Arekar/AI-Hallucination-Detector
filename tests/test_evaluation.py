import pytest

from app.evaluation import compare_predictions, evaluate_predictions


def test_classification_metrics_and_confusion_matrix_are_reproducible():
    report = evaluate_predictions(
        [
            {"expected": "SUPPORTED", "predicted": "SUPPORTED"},
            {"expected": "CONTRADICTED", "predicted": "SUPPORTED"},
            {"expected": "UNCERTAIN", "predicted": "UNCERTAIN"},
        ]
    )

    assert report["accuracy"] == pytest.approx(2 / 3)
    assert report["per_class"]["CONTRADICTED"]["recall"] == 0
    assert report["contradicted_false_negative_rate"] == 1
    assert report["confusion_matrix"]["CONTRADICTED"]["SUPPORTED"] == 1


def test_calibration_and_retrieval_metrics_use_only_labeled_inputs():
    report = evaluate_predictions(
        [
            {
                "expected": "SUPPORTED",
                "predicted": "SUPPORTED",
                "is_hallucination": 0,
                "hallucination_risk_score": 10,
                "expected_evidence_ids": ["a", "b"],
                "retrieved_evidence_ids": ["a", "x"],
            },
            {
                "expected": "CONTRADICTED",
                "predicted": "CONTRADICTED",
                "is_hallucination": 1,
                "hallucination_risk_score": 80,
                "expected_evidence_ids": ["c"],
                "retrieved_evidence_ids": ["c"],
            },
        ],
        bins=2,
    )

    assert report["calibration"]["brier_score"] == pytest.approx(0.025)
    assert report["calibration"]["expected_calibration_error"] == pytest.approx(0.15)
    assert report["evidence_retrieval"]["precision"] == pytest.approx(2 / 3)
    assert report["evidence_retrieval"]["recall"] == pytest.approx(2 / 3)


def test_comparison_uses_distinct_prediction_fields():
    result = compare_predictions(
        [
            {
                "expected": "SUPPORTED",
                "baseline_predicted": "UNCERTAIN",
                "improved_predicted": "SUPPORTED",
            }
        ]
    )

    assert result["baseline"]["accuracy"] == 0
    assert result["improved"]["accuracy"] == 1


def test_evaluation_reports_processing_time_and_provider_failures():
    report = evaluate_predictions(
        [
            {
                "expected": "SUPPORTED",
                "predicted": "SUPPORTED",
                "processing_ms": 100,
                "provider_failed": False,
            },
            {
                "expected": "CONTRADICTED",
                "predicted": "UNCERTAIN",
                "processing_ms": 300,
                "provider_failed": True,
            },
        ]
    )

    assert report["mean_processing_ms"] == 200
    assert report["processing_time_sample_count"] == 2
    assert report["provider_failure_rate"] == 0.5
    assert report["provider_failure_sample_count"] == 2


def test_invalid_or_empty_evaluation_data_is_rejected():
    with pytest.raises(ValueError):
        evaluate_predictions([])
    with pytest.raises(ValueError):
        evaluate_predictions([{"expected": "SUPPORTED", "predicted": "INVALID"}])
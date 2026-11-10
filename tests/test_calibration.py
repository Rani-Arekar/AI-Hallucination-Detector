import pytest

from app.detector.calibration import calibrate_score, fit_empirical_bins


def test_empirical_calibration_uses_held_out_labels():
    table = fit_empirical_bins([5, 15, 85, 95], [0, 1, 1, 1], bins=2)
    assert calibrate_score(10, table) == 0.5
    assert calibrate_score(90, table) == 1.0


def test_calibration_rejects_invalid_data():
    with pytest.raises(ValueError):
        fit_empirical_bins([10], [0, 1])
    with pytest.raises(ValueError):
        fit_empirical_bins([101], [1])
    with pytest.raises(ValueError):
        calibrate_score(-1, [])

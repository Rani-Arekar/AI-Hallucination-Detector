import pytest

from app.evaluation import normalize_fever_record


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("SUPPORTS", "SUPPORTED"),
        ("REFUTES", "CONTRADICTED"),
        ("NOT ENOUGH INFO", "UNVERIFIABLE"),
    ],
)
def test_fever_labels_are_mapped_without_inventing_uncertain(label, expected):
    record = {
        "id": 12,
        "label": label,
        "claim": "A factual claim.",
        "evidence": [[[1, 2, "Example_Page", 3]]],
    }

    normalized = normalize_fever_record(record, "validation")

    assert normalized["expected"] == expected
    assert normalized["expected_evidence_ids"] == ["Example_Page:3"]
    assert normalized["split"] == "validation"


def test_unlabeled_or_unknown_fever_labels_are_rejected():
    with pytest.raises(ValueError):
        normalize_fever_record({"id": 12, "claim": "An unlabeled claim."}, "test")
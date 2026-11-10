import pytest

from app.detector.scoring import aggregate_claim_scores, score_claim


def test_clearly_supported_claim_has_low_risk_and_evidence_confidence():
    result = score_claim(
        {
            "verdict": "SUPPORTED",
            "evidence_availability": "available",
            "evidence_items": [
                {
                    "source_type": "LOCAL KNOWLEDGE BASE",
                    "semantic_similarity": 0.95,
                    "url": None,
                },
                {
                    "source_type": "WEB SOURCE",
                    "semantic_similarity": None,
                    "url": "https://www.example.gov/fact",
                },
            ],
            "verification_reasoning": "Direct evidence supports the claim.",
        }
    )
    assert result["hallucination_risk"] == 0
    assert result["decision_confidence"] >= 70


def test_clearly_contradicted_claim_has_high_risk():
    result = score_claim(
        {
            "verdict": "CONTRADICTED",
            "evidence_availability": "available",
            "evidence_items": [
                {
                    "source_type": "WEB SOURCE",
                    "semantic_similarity": None,
                    "url": "https://www.example.edu/fact",
                }
            ],
        }
    )
    assert result["hallucination_risk"] == 100
    assert result["decision_confidence"] >= 50


def test_missing_evidence_is_not_scored_as_hallucinated():
    result = score_claim(
        {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "evidence_availability": "none",
            "evidence_items": [],
        }
    )
    assert result["hallucination_risk"] == 50
    assert result["decision_confidence"] < 30


def test_conflicting_evidence_remains_separate_from_confidence():
    result = score_claim(
        {
            "verdict": "UNCERTAIN",
            "evidence_availability": "available",
            "evidence_items": [
                {"source_type": "WEB SOURCE", "semantic_similarity": 0.8, "url": "https://a.org"},
                {"source_type": "WEB SOURCE", "semantic_similarity": 0.8, "url": "https://b.org"},
            ],
        }
    )
    assert result["hallucination_risk"] == 50
    assert 0 < result["decision_confidence"] < 100


def test_domain_suffix_alone_does_not_increase_source_credibility():
    base = {
        "verdict": "SUPPORTED",
        "evidence_availability": "available",
        "evidence_items": [
            {"source_type": "WEB SOURCE", "semantic_similarity": 0.8}
        ],
    }
    government_result = score_claim(
        {**base, "evidence_items": [{**base["evidence_items"][0], "url": "https://example.gov/fact"}]}
    )
    commercial_result = score_claim(
        {**base, "evidence_items": [{**base["evidence_items"][0], "url": "https://example.com/fact"}]}
    )

    assert government_result["signals"]["source_credibility"] == 0.5
    assert commercial_result["signals"]["source_credibility"] == 0.5
    assert government_result["decision_confidence"] == commercial_result["decision_confidence"]


def test_pages_from_one_publisher_are_not_independent_corroboration():
    result = score_claim(
        {
            "verdict": "SUPPORTED",
            "evidence_availability": "available",
            "evidence_items": [
                {"source_type": "FULL_WEBPAGE", "url": "https://example.org/a"},
                {"source_type": "FULL_WEBPAGE", "url": "https://example.org/b"},
            ],
        }
    )

    assert result["signals"]["source_agreement"] == 0.65


def test_multiple_claims_are_aggregated_and_countable():
    claims = [
        {"hallucination_risk": 0, "decision_confidence": 90},
        {"hallucination_risk": 100, "decision_confidence": 80},
        {"hallucination_risk": 50, "decision_confidence": 15},
    ]
    aggregate = aggregate_claim_scores(claims)
    assert aggregate["overall_hallucination_risk"] == 47
    assert aggregate["overall_reliability"] == 53


def test_aggregate_reports_evidence_coverage_and_verdict_shares():
    claims = [
        {"hallucination_risk": 0, "decision_confidence": 80, "verdict": "SUPPORTED", "evidence_availability": "available"},
        {"hallucination_risk": 100, "decision_confidence": 80, "verdict": "CONTRADICTED", "evidence_availability": "available"},
        {"hallucination_risk": 50, "decision_confidence": 20, "verdict": "PARTIALLY_SUPPORTED", "evidence_availability": "none"},
        {"hallucination_risk": 50, "decision_confidence": 15, "verdict": "INSUFFICIENT_EVIDENCE", "evidence_availability": "none"},
    ]

    aggregate = aggregate_claim_scores(claims)

    assert aggregate["evidence_coverage"] == 50
    assert aggregate["supported_claim_percentage"] == 25
    assert aggregate["contradicted_claim_percentage"] == 25
    assert aggregate["uncertain_claim_percentage"] == 25
    assert aggregate["unverifiable_claim_percentage"] == 25
    assert aggregate["retrieved_evidence_coverage"] == 50
    assert aggregate["resolved_reliability"] == 50
    assert aggregate["resolved_claim_count"] == 2
    assert aggregate["contradiction_rate"] == 25


def test_empty_aggregate_has_zero_coverage_and_percentages():
    aggregate = aggregate_claim_scores([])

    assert aggregate["evidence_coverage"] == 0
    assert aggregate["retrieved_evidence_coverage"] == 0
    assert aggregate["resolved_reliability"] is None
    assert aggregate["resolved_claim_count"] == 0
    assert aggregate["contradiction_rate"] == 0
    assert aggregate["supported_claim_percentage"] == 0
    assert aggregate["contradicted_claim_percentage"] == 0
    assert aggregate["uncertain_claim_percentage"] == 0
    assert aggregate["unverifiable_claim_percentage"] == 0


def test_invalid_module_score_is_rejected():
    from app.detector.scoring import compute_final_score

    with pytest.raises(ValueError):
        compute_final_score(
            {"fact": 2, "logic": 1, "citation": 1, "confidence": 1, "cross": 1}
        )


def test_external_verification_failure_can_be_unverifiable():
    result = score_claim(
        {
            "verdict": "UNCERTAIN",
            "evidence_availability": "none",
            "evidence_items": [],
            "verification_reasoning": "Verifier failed before evidence could be assessed.",
        }
    )
    assert result["hallucination_risk"] == 50
    assert "failed" in result["verification_reasoning"]


def test_verification_provider_failure_is_not_collapsed_into_missing_evidence():
    result = score_claim(
        {
            "verdict": "UNCERTAIN",
            "evidence_availability": "verification_unavailable",
            "evidence_items": [],
        }
    )

    assert result["evidence_availability"] == "verification_unavailable"

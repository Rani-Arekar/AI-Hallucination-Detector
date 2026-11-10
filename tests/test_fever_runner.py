from unittest.mock import AsyncMock, patch

import pytest

from run_fever_benchmark import predict_records


@pytest.mark.asyncio
@patch("run_fever_benchmark.fact_check_claims", new_callable=AsyncMock)
async def test_partial_verdict_maps_to_uncertain_and_keeps_evidence(mock_check):
    mock_check.return_value = (
        [
            {
                "verdict": "PARTIALLY_SUPPORTED",
                "evidence_availability": "available",
                "evidence_items": [
                    {
                        "text": "A supporting excerpt.",
                        "url": "https://example.org/source",
                        "relation": "supports",
                    }
                ],
            }
        ],
        0.6,
    )
    rows = [{"id": 1, "split": "validation", "expected": "SUPPORTED", "text": "Claim"}]

    result = await predict_records(rows, "both", 1)

    assert result[0]["predicted"] == "UNCERTAIN"
    assert "improved_predicted" not in result[0]
    assert result[0]["retrieved_evidence"][0]["url"] == "https://example.org/source"
    assert result[0]["processing_ms"] >= 0
    assert result[0]["provider_failed"] is False
    assert mock_check.await_args.kwargs["use_web_search"] is True


@pytest.mark.asyncio
async def test_runner_rejects_non_positive_limits():
    with pytest.raises(ValueError):
        await predict_records([], "both", 0)
from unittest.mock import AsyncMock, patch

import pytest

from app.detector.claims import ClaimExtractionOutcome, ExtractedClaim
from app.detector.pipeline import run_detection


@pytest.mark.asyncio
@patch("app.detector.pipeline.extract_claims_with_status")
@patch("app.detector.pipeline.fact_check_claims", new_callable=AsyncMock)
@patch("app.detector.pipeline.logic_score_async", new_callable=AsyncMock)
@patch("app.detector.pipeline.cross_model_score_async", new_callable=AsyncMock)
async def test_standard_mode_runs_all_stages(
    mock_cross, mock_logic, mock_fact, mock_extract
):
    mock_extract.return_value = ClaimExtractionOutcome([
        ExtractedClaim(
            text="claim one",
            source_text="answer text",
            start_offset=0,
            end_offset=len("answer text"),
            category="historical",
            dates=["1066"],
        )
    ], "complete")
    mock_fact.return_value = ([{"claim": "claim one", "verdict": "SUPPORTED", "score": 1.0}], 1.0)
    mock_logic.return_value = 1.0
    mock_cross.return_value = 1.0

    report = await run_detection("prompt", "answer text", mode="standard")

    mock_fact.assert_awaited_once()
    mock_logic.assert_awaited_once()
    mock_cross.assert_awaited_once()

    assert report["mode"] == "standard"
    assert "risk_score" in report
    assert 0 <= report["risk_score"] <= 100
    assert set(report["module_scores"].keys()) == {"fact", "logic", "citation", "confidence", "cross"}
    assert "total_ms" in report["latency"]
    assert "evidence_and_verification_ms" in report["latency"]
    assert report["claims"][0]["source_text"] == "answer text"
    assert report["claims"][0]["dates"] == ["1066"]
    assert report["claim_extraction_status"] == "complete"
    assert mock_fact.call_args.kwargs["claim_contexts"][0]["dates"] == ["1066"]


@pytest.mark.asyncio
@patch("app.detector.pipeline.extract_claims_with_status")
@patch("app.detector.pipeline.fact_check_claims", new_callable=AsyncMock)
@patch("app.detector.pipeline.logic_score_async", new_callable=AsyncMock)
@patch("app.detector.pipeline.cross_model_score_async", new_callable=AsyncMock)
async def test_quick_mode_skips_logic_and_cross_model(
    mock_cross, mock_logic, mock_fact, mock_extract
):
    mock_extract.return_value = ClaimExtractionOutcome([
        ExtractedClaim(
            text="claim one",
            source_text="answer text",
            start_offset=0,
            end_offset=len("answer text"),
        )
    ], "complete")
    mock_fact.return_value = ([], 1.0)

    report = await run_detection("prompt", "answer text", mode="quick")

    # quick mode shouldn't call the logic or cross-model verifiers at all
    mock_logic.assert_not_called()
    mock_cross.assert_not_called()
    # but fact_check_claims should still be called, with web search disabled
    args, kwargs = mock_fact.call_args
    assert kwargs["use_web_search"] is False

    assert report["module_scores"]["logic"] == 1.0
    assert report["module_scores"]["cross"] == 1.0


@pytest.mark.asyncio
@patch("app.detector.pipeline.extract_claims_with_status")
@patch("app.detector.pipeline.fact_check_claims", new_callable=AsyncMock)
async def test_no_claims_extracted_still_returns_a_report(mock_fact, mock_extract):
    mock_extract.return_value = ClaimExtractionOutcome([], "empty_input")
    mock_fact.return_value = ([], 1.0)

    report = await run_detection("prompt", "", mode="quick")

    assert report["claims"] == []
    assert report["claim_extraction_status"] == "empty_input"
    assert isinstance(report["risk_score"], int)

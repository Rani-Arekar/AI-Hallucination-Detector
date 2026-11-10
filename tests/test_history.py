from app.history import analytics, delete_analyses, get_analysis, list_analyses, save_analysis


def _response(analysis_id: str) -> dict:
    return {
        "analysisId": analysis_id,
        "reliabilityScore": 80,
        "hallucinationRiskScore": 20,
        "decisionConfidence": 90,
        "scoreType": "heuristic",
        "claims": [{
            "id": f"{analysis_id}-claim",
            "text": "A claim",
            "status": "supported",
            "hallucinationRiskScore": 5,
            "decisionConfidence": 95,
            "explanation": "Evidence supports it.",
            "evidence": [],
        }],
    }


def test_history_respects_input_privacy_and_calculates_analytics():
    analysis_id = "history-test-privacy"
    save_analysis("history-test-owner", "private input", _response(analysis_id), "standard", "both", False)
    record = get_analysis("history-test-owner", analysis_id)
    assert record is not None
    assert record.original_input is None
    assert record.title == "Saved analysis"
    assert record.preview == ""
    assert list_analyses("history-test-owner")[0].id == analysis_id
    assert analytics("history-test-owner")["totalAnalyses"] == 1
    delete_analyses("history-test-owner", [analysis_id])
    assert get_analysis("history-test-owner", analysis_id) is None

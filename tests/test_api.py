from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    # main._rate_limiter is a module-level singleton so its state persists
    # across tests unless reset -- avoid cross-test flakiness.
    main._rate_limiter._hits.clear()
    yield
    main._rate_limiter._hits.clear()


@pytest.fixture
def client():
    return TestClient(main.app)


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "kb_documents" in body
    assert body["gemini_configured"] is True


def test_health_remains_available_without_gemini_credentials(client, monkeypatch):
    monkeypatch.setattr(main, "GEMINI_API_KEY", None)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["gemini_configured"] is False


def test_analyze_reports_missing_gemini_credentials(client, monkeypatch):
    monkeypatch.setattr(main, "GEMINI_API_KEY", None)
    response = client.post("/api/analyze", json={"text": "The Earth is round.", "save_history": False})
    assert response.status_code == 503
    assert "credentials" in response.json()["detail"]


def test_empty_prompt_rejected(client):
    resp = client.post("/ask", json={"prompt": ""})
    assert resp.status_code == 422


def test_whitespace_only_prompt_rejected(client):
    resp = client.post("/ask", json={"prompt": "   "})
    assert resp.status_code == 422


def test_oversized_prompt_rejected(client):
    resp = client.post("/ask", json={"prompt": "x" * 5000})
    assert resp.status_code == 422


def test_invalid_mode_rejected(client):
    resp = client.post("/ask", json={"prompt": "hello", "mode": "ultra"})
    assert resp.status_code == 422


@patch("main.run_detection", new_callable=AsyncMock)
@patch("main.generate_answer_async", new_callable=AsyncMock)
def test_ask_happy_path(mock_generate, mock_run_detection, client):
    mock_generate.return_value = "The Eiffel Tower was completed in 1889."
    mock_run_detection.return_value = {
        "risk_score": 10,
        "module_scores": {"fact": 1.0, "logic": 1.0, "citation": 0.5, "confidence": 1.0, "cross": 1.0},
        "claims": [{"claim": "The Eiffel Tower was completed in 1889.", "verdict": "SUPPORTED", "score": 1.0}],
        "mode": "standard",
        "latency": {"claim_extraction_ms": 1.0},
    }

    resp = client.post("/ask", json={"prompt": "When was the Eiffel Tower built?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "The Eiffel Tower was completed in 1889."
    assert body["risk_score"] == 10
    assert "generation_ms" in body["latency"]
    assert "total_ms" in body["latency"]


@patch("main.run_detection", new_callable=AsyncMock)
@patch("main.generate_answer_async", new_callable=AsyncMock)
def test_ask_defaults_to_standard_mode(mock_generate, mock_run_detection, client):
    mock_generate.return_value = "answer"
    mock_run_detection.return_value = {
        "risk_score": 0,
        "module_scores": {},
        "claims": [],
        "mode": "standard",
        "latency": {},
    }

    client.post("/ask", json={"prompt": "hello"})

    _, kwargs = mock_run_detection.call_args
    # mode passed positionally in main.py -- check via call_args directly
    called_args = mock_run_detection.call_args.args
    called_kwargs = mock_run_detection.call_args.kwargs
    assert called_kwargs.get("mode", called_args[-1] if called_args else None) == "standard"


@patch("main.run_detection", new_callable=AsyncMock)
def test_analyze_accepts_existing_text(mock_run_detection, client):
    mock_run_detection.return_value = {
        "risk_score": 25,
        "module_scores": {
            "fact": 0.8,
            "logic": 1.0,
            "citation": 0.5,
            "confidence": 1.0,
            "cross": 1.0,
        },
        "claims": [
            {
                "claim": "The answer contains a factual claim.",
                "claim_id": "claim-1",
                "verdict": "SUPPORTED",
                "score": 1.0,
                "evidence": "A relevant source.",
                "sources": [],
                "hallucination_risk": 0,
                "decision_confidence": 80,
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "semantic_similarity_signals": [],
                "verification_reasoning": "The evidence supports the claim.",
                "evidence_availability": "available",
                "signals": {},
                "source_text": "The answer contains a factual claim.",
                "start_offset": 0,
                "end_offset": len("The answer contains a factual claim."),
                "category": "historical",
                "entities": [{"text": "Example", "kind": "person"}],
                "dates": ["1066"],
                "quantities": [],
                "relationships": [],
                "context_dependent": False,
                "context_evidence": [{
                    "text": "The original sentence gives context.",
                    "source_type": "WEB SOURCE",
                    "title": "Reference page",
                    "url": "https://example.org/reference",
                    "retrieved_at": "2026-11-08T12:00:00+00:00",
                    "relation": "context",
                }],
            }
        ],
        "citations": [],
        "mode": "standard",
        "latency": {},
        "overall_reliability": 75,
        "overall_hallucination_risk": 25,
        "overall_decision_confidence": 80,
        "evidence_coverage": 100,
        "retrieved_evidence_coverage": 100,
        "resolved_reliability": 100,
        "resolved_claim_count": 1,
        "contradiction_rate": 0,
        "claim_extraction_status": "complete",
        "total_factual_claims": 1,
        "claim_counts": {
            "supported": 1,
            "contradicted": 0,
            "uncertain": 0,
            "unverifiable": 0,
        },
        "scoring_methodology_version": "claim-heuristic-v1",
    }

    resp = client.post(
        "/api/analyze",
        json={
            "text": "The answer contains a factual claim.",
            "evidence_source": "knowledge-base",
            "claim_granularity": "sentence",
            "confidence_threshold": 80,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["analysisId"].startswith("analysis-")
    assert body["reliabilityScore"] == 75
    assert body["hallucinationRiskScore"] == 25
    assert body["decisionConfidence"] == 80
    assert body["scoreType"] == "heuristic"
    assert body["totalClaims"] == 1
    assert body["supportedClaims"] == 1
    assert body["contradictedClaims"] == 0
    assert body["uncertainClaims"] == 0
    assert body["unverifiableClaims"] == 0
    assert body["claims"][0]["status"] == "supported"
    assert body["claims"][0]["hallucinationRiskScore"] == 0
    assert len(body["claims"][0]["evidence"]) == 1
    assert body["claims"][0]["sourceText"] == "The answer contains a factual claim."
    assert body["claims"][0]["startOffset"] == 0
    assert body["claims"][0]["endOffset"] == len("The answer contains a factual claim.")
    assert body["claims"][0]["claimType"] == "historical"
    assert body["claims"][0]["dates"] == ["1066"]
    assert body["claims"][0]["evidence"][0]["relation"] == "context"
    assert body["claims"][0]["evidence"][0]["text"] == "The original sentence gives context."
    assert body["claims"][0]["evidence"][0]["retrievedAt"] == "2026-11-08T12:00:00+00:00"
    assert body["claimExtractionStatus"] == "complete"
    assert body["evidenceCoverage"] == 100
    assert body["resolvedReliabilityScore"] == 100
    assert body["resolvedClaimCount"] == 1
    second = client.post(
        "/api/analyze",
        json={"text": "Another factual claim."},
    )
    assert second.json()["analysisId"] != body["analysisId"]
    assert mock_run_detection.await_count == 2
    assert mock_run_detection.call_args_list[0].kwargs["claim_granularity"] == "sentence"


@patch("main.run_detection", new_callable=AsyncMock)
def test_extraction_failure_is_not_reported_as_no_factual_claims(mock_run_detection, client):
    mock_run_detection.return_value = {
        "claims": [],
        "overall_reliability": 50,
        "overall_hallucination_risk": 50,
        "overall_decision_confidence": 0,
        "evidence_coverage": 0,
        "retrieved_evidence_coverage": 0,
        "resolved_reliability": None,
        "resolved_claim_count": 0,
        "contradiction_rate": 0,
        "claim_extraction_status": "invalid_response",
        "latency": {},
    }

    response = client.post("/api/analyze", json={"text": "A factual statement.", "save_history": False})

    assert response.status_code == 200
    assert response.json()["totalClaims"] == 0
    assert response.json()["claimExtractionStatus"] == "invalid_response"
    assert response.json()["resolvedReliabilityScore"] is None


@pytest.mark.parametrize(
    ("text", "verdict", "expected_status", "risk"),
    [
        ("The Battle of Hastings occurred in 1066.", "SUPPORTED", "supported", 5),
        ("The Battle of Hastings occurred in 1067.", "CONTRADICTED", "contradicted", 100),
        ("The Battle of Hastings occurred in 1066 and aliens built the castle.", "UNCERTAIN", "uncertain", 50),
        ("This claim cannot be checked from available sources.", "INSUFFICIENT_EVIDENCE", "unverifiable", 50),
    ],
)
@patch("main.run_detection", new_callable=AsyncMock)
def test_analyze_classifies_factual_and_unverifiable_cases(
    mock_run_detection, client, text, verdict, expected_status, risk
):
    mock_run_detection.return_value = {
        "claims": [{
            "claim": text,
            "verdict": verdict,
            "hallucination_risk": risk,
            "decision_confidence": 80,
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "verification_reasoning": "Test verification reasoning.",
        }],
        "overall_reliability": 100 - risk,
        "overall_hallucination_risk": risk,
        "overall_decision_confidence": 80,
        "latency": {},
    }
    response = client.post("/api/analyze", json={"text": text, "save_history": False})
    assert response.status_code == 200
    claim = response.json()["claims"][0]
    assert claim["status"] == expected_status
    assert 0 <= claim["hallucinationRiskScore"] <= 100
    assert 0 <= claim["decisionConfidence"] <= 100


def test_oversized_body_rejected_before_parsing(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_REQUEST_BODY_BYTES", 1024)
    huge_prompt = "x" * 2048
    resp = client.post("/ask", json={"prompt": huge_prompt})
    assert resp.status_code == 413


def test_rate_limit_blocks_after_threshold(client):
    # Tighten the limiter just for this test so it doesn't need 20+ requests.
    original_max = main._rate_limiter.max_requests
    main._rate_limiter.max_requests = 2
    try:
        with patch("main.run_detection", new_callable=AsyncMock) as mock_run_detection, patch(
            "main.generate_answer_async", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.return_value = "answer"
            mock_run_detection.return_value = {
                "risk_score": 0,
                "module_scores": {},
                "claims": [],
                "mode": "standard",
                "latency": {},
            }

            r1 = client.post("/ask", json={"prompt": "one"})
            r2 = client.post("/ask", json={"prompt": "two"})
            r3 = client.post("/ask", json={"prompt": "three"})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
        assert "Retry-After" in r3.headers
    finally:
        main._rate_limiter.max_requests = original_max


def test_health_endpoint_not_rate_limited(client):
    # Tighten the limiter, but /health should be exempt.
    original_max = main._rate_limiter.max_requests
    main._rate_limiter.max_requests = 1
    try:
        for _ in range(5):
            resp = client.get("/health")
            assert resp.status_code == 200
    finally:
        main._rate_limiter.max_requests = original_max


def test_cors_allows_history_delete_from_frontend(client):
    response = client.options(
        "/api/history/example",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-methods"]
    assert "DELETE" in response.headers["access-control-allow-methods"]


def test_unhandled_exception_returns_safe_generic_message():
    # raise_server_exceptions=False: by default TestClient re-raises
    # exceptions instead of returning the response, specifically so bugs
    # don't hide silently in tests. Here we're deliberately testing that
    # the registered handler converts it to a safe response, so we need
    # the client to actually hand back that response instead of re-raising.
    client = TestClient(main.app, raise_server_exceptions=False)
    with patch("main.generate_answer_async", new_callable=AsyncMock) as mock_generate:
        mock_generate.side_effect = RuntimeError("some internal secret detail")
        resp = client.post("/ask", json={"prompt": "hello"})

    assert resp.status_code == 500
    body = resp.json()
    assert body == {"error": "internal server error"}
    # the actual exception message must never reach the client
    assert "some internal secret detail" not in resp.text


def test_cors_headers_reflect_allowed_origin(client):
    allowed_origin = main.ALLOWED_ORIGINS[0]
    resp = client.get("/health", headers={"Origin": allowed_origin})
    assert resp.headers.get("access-control-allow-origin") == allowed_origin


def test_cors_rejects_disallowed_origin(client):
    resp = client.get(
        "/health",
        headers={"Origin": "https://not-an-allowed-origin.example.com"},
    )
    # CORSMiddleware simply omits the allow-origin header for a disallowed
    # origin rather than blocking the request server-side (browsers enforce
    # the block); this asserts that we didn't reflect the disallowed origin.
    assert resp.headers.get("access-control-allow-origin") != "https://not-an-allowed-origin.example.com"

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.detector.fact_check import (
    _parse_verification_response,
    _verification_prompt,
    fact_check_claims,
)
from app.detector.corrections import generate_verified_correction
from app.vector_db.simple_store import SimpleVectorStore


def _hybrid_result(text: str, semantic_similarity: float = 0.9) -> dict:
    return {
        "text": text,
        "semantic_similarity": semantic_similarity,
        "keyword_score": 1.0,
        "retrieval_score": 0.03,
    }


def test_keyword_retrieval_prioritizes_exact_entities_and_numbers():
    store = SimpleVectorStore()
    store.docs = [
        "The Battle of Hastings occurred in 1066.",
        "A medieval battle took place in England.",
    ]

    results = store.query_keyword("Hastings 1066", k=2)

    assert results == [(results[0][0], store.docs[0])]
    assert results[0][0] > 0


def test_partial_verdict_is_not_promoted_to_supported():
    verdict, relevant, supporting, contradicting, valid = _parse_verification_response(
        '{"verdict": "PARTIALLY_SUPPORTED", "relevant_candidates": [1], "supporting_candidates": [1], "contradicting_candidates": []}'
    )

    assert valid is True
    assert verdict == "PARTIALLY_SUPPORTED"
    assert relevant == [1]
    assert supporting == [1]
    assert contradicting == []


def test_uncertain_verdict_is_valid():
    verdict, relevant, supporting, contradicting, valid = _parse_verification_response(
        '{"verdict": "UNCERTAIN", "relevant_candidates": [1]}'
    )

    assert valid is True
    assert verdict == "UNCERTAIN"
    assert relevant == [1]
    assert supporting == []
    assert contradicting == []


def test_malformed_verifier_response_fails_closed():
    verdict, relevant, supporting, contradicting, valid = _parse_verification_response(
        "not JSON, but it says SUPPORTED"
    )

    assert valid is False
    assert verdict == "UNCERTAIN"
    assert relevant == []
    assert supporting == []
    assert contradicting == []


def test_verification_prompt_includes_available_source_metadata():
    prompt = _verification_prompt(
        "A claim.",
        None,
        [
            {
                "content": "Evidence excerpt.",
                "source": "FULL_WEBPAGE",
                "title": "Reference",
                "publisher": "example.org",
                "author": "Researcher",
                "published_at": "2024-01-02",
                "url": "https://example.org/article",
            }
        ],
    )

    assert "Publisher: example.org" in prompt
    assert "Author: Researcher" in prompt
    assert "Published: 2024-01-02" in prompt
    assert "do not" in prompt.lower()


def test_verdict_conflicting_with_directional_evidence_is_uncertain():
    raw = (
        '{"verdict": "SUPPORTED", "relevant_candidates": [1], '
        '"supporting_candidates": [], "contradicting_candidates": [1]}'
    )
    verdict, relevant, supporting, contradicting, valid = _parse_verification_response(raw)

    assert valid is True
    assert verdict == "UNCERTAIN"
    assert relevant == [1]
    assert supporting == []
    assert contradicting == [1]


@pytest.mark.asyncio
@patch("app.detector.corrections.verify_prompt_async", new_callable=AsyncMock)
async def test_correction_is_returned_only_after_second_verification(mock_verify):
    mock_verify.side_effect = [
        '{"correction": "The museum is open on Sundays.", "evidence_candidates": [1]}',
        '{"verdict": "SUPPORTED", "supporting_candidates": [1]}',
    ]

    correction = await generate_verified_correction(
        "The museum is closed on Sundays.",
        [{"text": "The museum is open on Sundays.", "title": "Hours", "url": "https://museum.example/hours"}],
    )

    assert correction is not None
    assert correction["text"] == "The museum is open on Sundays."
    assert correction["evidence"][0]["url"] == "https://museum.example/hours"
    assert mock_verify.await_count == 2


@pytest.mark.asyncio
@patch("app.detector.corrections.verify_prompt_async", new_callable=AsyncMock)
async def test_unverified_correction_is_not_returned(mock_verify):
    mock_verify.side_effect = [
        '{"correction": "The museum is open on Sundays.", "evidence_candidates": [1]}',
        '{"verdict": "UNCERTAIN", "supporting_candidates": []}',
    ]

    correction = await generate_verified_correction(
        "The museum is closed on Sundays.",
        [{"text": "The museum has a gift shop.", "title": "About", "url": "https://museum.example/about"}],
    )

    assert correction is None


@pytest.mark.asyncio
async def test_no_claims_returns_default_score():
    results, score = await fact_check_claims([])
    assert results == []
    assert score == 1.0


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_no_evidence_gives_insufficient_evidence_verdict(
    mock_verify, mock_search, mock_store
):
    mock_store.query_hybrid.return_value = []
    mock_search.return_value = []

    results, score = await fact_check_claims(["Some unverifiable claim"], use_web_search=True)

    assert len(results) == 1
    assert results[0]["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert results[0]["evidence"] is None
    # verifier should never be called when there's no evidence to give it
    mock_verify.assert_not_called()


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_extracted_context_is_included_in_local_and_web_queries(
    mock_verify, mock_search, mock_store
):
    mock_store.query_hybrid.return_value = [
        _hybrid_result("John McCarthy proposed the term artificial intelligence in 1955.")
    ]
    mock_search.return_value = []
    mock_verify.return_value = '{"verdict": "SUPPORTED", "relevant_candidates": [1]}'
    context = {
        "source_text": "John McCarthy proposed the term AI in 1955.",
        "entities": [{"text": "John McCarthy", "kind": "person"}],
        "dates": ["1955"],
    }

    await fact_check_claims(
        ["He proposed the term AI."],
        use_web_search=True,
        claim_contexts=[context],
    )

    local_query = mock_store.query_hybrid.call_args.args[0]
    web_query = mock_search.await_args.args[0]
    for query in (local_query, web_query):
        assert "John McCarthy" in query
        assert "1955" in query


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_empty_primary_search_retries_once_with_entity_date_query(
    mock_verify, mock_search, mock_store
):
    mock_store.query_hybrid.return_value = []
    mock_search.side_effect = [
        [],
        [{"title": "Dartmouth history", "url": "https://example.org", "body": "The workshop was held in 1956."}],
    ]
    mock_verify.return_value = '{"verdict": "SUPPORTED", "relevant_candidates": [1]}'
    context = {
        "source_text": "The Dartmouth workshop established the field in 1956.",
        "entities": [{"text": "Dartmouth", "kind": "organization"}],
        "dates": ["1956"],
    }

    results, _ = await fact_check_claims(
        ["The workshop established the field."],
        use_knowledge_base=False,
        claim_contexts=[context],
    )

    assert results[0]["verdict"] == "SUPPORTED"
    assert mock_search.await_count == 2
    fallback_query = mock_search.await_args.args[0]
    assert "Dartmouth" in fallback_query
    assert "1956" in fallback_query


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_web_retrieval_timestamp_is_preserved_in_evidence(
    mock_verify, mock_search, mock_store
):
    retrieved_at = "2026-11-08T12:00:00+00:00"
    mock_store.query_hybrid.return_value = []
    mock_search.return_value = [
        {
            "title": "Reference",
            "url": "https://example.org/reference",
            "body": "A relevant factual excerpt.",
            "retrieved_at": retrieved_at,
        }
    ]
    mock_verify.return_value = '{"verdict": "SUPPORTED", "relevant_candidates": [1]}'

    results, _ = await fact_check_claims(["A factual claim."], use_knowledge_base=False)

    assert results[0]["evidence_items"][0]["retrieved_at"] == retrieved_at


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
async def test_retrieval_failure_logs_do_not_include_claim_text(mock_search, mock_store, caplog):
    private_claim = "Private sentence from an unpublished report"
    mock_store.query_hybrid.side_effect = RuntimeError(private_claim)
    mock_search.return_value = []

    await fact_check_claims([private_claim], use_web_search=False)

    assert private_claim not in caplog.text


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_supported_verdict_scores_full_marks(mock_verify, mock_search, mock_store):
    mock_store.query_hybrid.return_value = [
        _hybrid_result("The Eiffel Tower was completed in 1889.")
    ]
    mock_search.return_value = []
    mock_verify.return_value = '{"verdict": "SUPPORTED", "relevant_candidates": [1]}'

    results, score = await fact_check_claims(["The Eiffel Tower was completed in 1889."])

    assert results[0]["verdict"] == "SUPPORTED"
    assert results[0]["score"] == 1.0
    assert score == 1.0


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_contradicted_verdict_scores_zero(mock_verify, mock_search, mock_store):
    mock_store.query_hybrid.return_value = [
        _hybrid_result("The Eiffel Tower is 500 meters tall.")
    ]
    mock_search.return_value = []
    mock_verify.return_value = '{"verdict": "CONTRADICTED", "relevant_candidates": [1]}'

    results, score = await fact_check_claims(["The Eiffel Tower is 50 meters tall."])

    assert results[0]["verdict"] == "CONTRADICTED"
    assert results[0]["score"] == 0.0


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_one_failing_claim_does_not_crash_the_others(mock_verify, mock_search, mock_store):
    mock_store.query_hybrid.side_effect = [
        RuntimeError("KB is on fire"),  # claim 1: KB lookup blows up
        [_hybrid_result("Python was created by Guido van Rossum.")],  # claim 2: fine
    ]
    mock_search.return_value = []
    mock_verify.return_value = '{"verdict": "SUPPORTED", "relevant_candidates": [1]}'

    results, score = await fact_check_claims(
        ["claim that breaks", "Python was created by Guido van Rossum."]
    )

    assert len(results) == 2
    # claim 1's KB failure degrades to "no evidence", not a crash
    assert results[0]["verdict"] == "INSUFFICIENT_EVIDENCE"
    # claim 2 still gets fully processed
    assert results[1]["verdict"] == "SUPPORTED"


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
async def test_web_search_skipped_when_disabled(mock_search, mock_store):
    mock_store.query_hybrid.return_value = [_hybrid_result("some KB doc")]
    with patch(
        "app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock
    ) as mock_verify:
        mock_verify.return_value = '{"verdict": "SUPPORTED", "relevant_candidates": [1]}'
        await fact_check_claims(["a claim"], use_web_search=False)

    mock_search.assert_not_called()


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_web_sources_are_populated_with_title_and_url(mock_verify, mock_search, mock_store):
    mock_store.query_hybrid.return_value = []
    mock_search.return_value = [
        {"title": "Eiffel Tower - Wikipedia", "url": "https://en.wikipedia.org/wiki/Eiffel_Tower", "body": "Completed in 1889."}
    ]
    mock_verify.return_value = '{"verdict": "SUPPORTED", "relevant_candidates": [1]}'

    results, _ = await fact_check_claims(["The Eiffel Tower was completed in 1889."])

    assert results[0]["sources"] == [
        {"title": "Eiffel Tower - Wikipedia", "url": "https://en.wikipedia.org/wiki/Eiffel_Tower"}
    ]
    assert "Completed in 1889." in results[0]["evidence"]

@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_structured_verifier_selects_relevant_evidence(
    mock_verify, mock_search, mock_store
):
    mock_store.query_hybrid.return_value = [
        _hybrid_result("The Eiffel Tower is 330 meters tall.")
    ]
    mock_search.return_value = [
        {
            "title": "Eiffel Tower - Wikipedia",
            "url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
            "body": "The Eiffel Tower is 330 meters tall.",
        }
    ]

    mock_verify.return_value = (
        '{"verdict": "SUPPORTED", "relevant_candidates": [1]}'
    )

    results, _ = await fact_check_claims(
        ["The Eiffel Tower is 330 meters tall."],
        use_web_search=True,
    )

    assert results[0]["verdict"] == "SUPPORTED"
    assert results[0]["evidence"] == (
        "The Eiffel Tower is 330 meters tall."
    )
    assert results[0]["sources"] == [
        {
            "title": "Eiffel Tower - Wikipedia",
            "url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
        }
    ]


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_structured_verifier_excludes_irrelevant_candidates(
    mock_verify, mock_search, mock_store
):
    mock_store.query_hybrid.return_value = [
        _hybrid_result("The Eiffel Tower is 330 meters tall."),
    ]
    mock_search.return_value = [
        {
            "title": "New Delhi - Wikipedia",
            "url": "https://en.wikipedia.org/wiki/New_Delhi",
            "body": "New Delhi is the capital city of India.",
        }
    ]

    mock_verify.return_value = (
        '{"verdict": "SUPPORTED", "relevant_candidates": [2]}'
    )

    results, _ = await fact_check_claims(
        ["The capital of India is New Delhi."],
        use_web_search=True,
    )

    assert results[0]["verdict"] == "SUPPORTED"
    assert results[0]["evidence"] == "New Delhi is the capital city of India."
    assert "Eiffel Tower" not in results[0]["evidence"]
    assert results[0]["sources"] == [
        {
            "title": "New Delhi - Wikipedia",
            "url": "https://en.wikipedia.org/wiki/New_Delhi",
        }
    ]


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_irrelevant_web_results_trigger_bounded_contextual_retry(
    mock_verify, mock_search, mock_store
):
    mock_store.query_hybrid.return_value = []
    mock_search.side_effect = [
        [
            {
                "title": "Unrelated page",
                "url": "https://example.org/unrelated",
                "body": "This page is unrelated to the workshop.",
            }
        ],
        [
            {
                "title": "Workshop archive",
                "url": "https://example.org/archive",
                "body": "The 1956 workshop was held at Dartmouth College.",
            }
        ],
    ]
    mock_verify.side_effect = [
        '{"verdict": "NO_RELEVANT_EVIDENCE", "relevant_candidates": []}',
        '{"verdict": "SUPPORTED", "relevant_candidates": [2]}',
    ]
    context = {
        "source_text": "The 1956 Dartmouth workshop was held at Dartmouth College.",
        "entities": [{"text": "Dartmouth", "kind": "organization"}],
        "dates": ["1956"],
    }

    results, _ = await fact_check_claims(
        ["The workshop was held at Dartmouth."],
        use_knowledge_base=False,
        claim_contexts=[context],
    )

    assert results[0]["verdict"] == "SUPPORTED"
    assert len(mock_search.await_args_list) == 2
    assert "Dartmouth" in mock_search.await_args_list[1].args[0]
    assert results[0]["evidence_items"][0]["url"] == "https://example.org/archive"


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_verifier_candidate_index_outside_retrieval_is_unavailable(
    mock_verify, mock_search, mock_store
):
    mock_store.query_hybrid.return_value = [_hybrid_result("Relevant evidence.")]
    mock_search.return_value = []
    mock_verify.return_value = '{"verdict": "SUPPORTED", "relevant_candidates": [2]}'

    results, _ = await fact_check_claims(["A claim."], use_web_search=False)

    assert results[0]["verdict"] == "UNCERTAIN"
    assert results[0]["evidence_availability"] == "verification_unavailable"
    assert results[0]["evidence_items"] == []


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_conflicting_evidence_returns_uncertain_with_both_sides(
    mock_verify, mock_search, mock_store
):
    mock_store.query_hybrid.return_value = [_hybrid_result("The museum is closed on Sundays.")]
    mock_search.return_value = [
        {
            "title": "Museum visitor information",
            "url": "https://museum.example/visit",
            "body": "The museum is open on Sundays.",
        }
    ]
    mock_verify.return_value = (
        '{"verdict": "SUPPORTED", "relevant_candidates": [1, 2], '
        '"supporting_candidates": [2], "contradicting_candidates": [1]}'
    )

    results, _ = await fact_check_claims(
        ["The museum is open on Sundays."], use_web_search=True
    )

    assert results[0]["verdict"] == "UNCERTAIN"
    assert [item["relation"] for item in results[0]["evidence_items"]] == [
        "contradicts",
        "supports",
    ]


@pytest.mark.parametrize(
    ("claim", "evidence", "verdict"),
    [
        (
            "Machine learning is a subset of artificial intelligence.",
            "Machine learning is a subfield of artificial intelligence.",
            "SUPPORTED",
        ),
        (
            "Deep learning is a subset of machine learning.",
            "Deep learning is a specialized area within machine learning.",
            "SUPPORTED",
        ),
        (
            "John McCarthy proposed the term artificial intelligence in 1955.",
            "John McCarthy proposed the term artificial intelligence in 1955.",
            "SUPPORTED",
        ),
        (
            "The 1956 Dartmouth workshop helped establish artificial intelligence as a field.",
            "The 1956 Dartmouth Summer Research Project is widely regarded as a founding event for AI as a field.",
            "SUPPORTED",
        ),
        (
            "The 1956 Dartmouth workshop was held at Stanford University.",
            "The 1956 Dartmouth workshop was held at Dartmouth College.",
            "CONTRADICTED",
        ),
        (
            "Python was created by James Gosling.",
            "Python was created by Guido van Rossum.",
            "CONTRADICTED",
        ),
        (
            "ENIAC was developed by J. Presper Eckert and John Mauchly.",
            "ENIAC was developed by J. Presper Eckert and John Mauchly.",
            "SUPPORTED",
        ),
        (
            "ENIAC was completed in 1945.",
            "ENIAC was completed in 1945 and publicly unveiled in 1946.",
            "SUPPORTED",
        ),
        (
            "ENIAC was publicly unveiled in 1945.",
            "ENIAC was completed in 1945 and publicly unveiled in 1946.",
            "CONTRADICTED",
        ),
        (
            "Alan Turing's 1950 paper introduced the imitation game.",
            "In his 1950 paper Computing Machinery and Intelligence, Alan Turing proposed the imitation game.",
            "SUPPORTED",
        ),
        (
            "Alan Turing called the imitation game the Turing Test in his 1950 paper.",
            "The 1950 paper called it the imitation game; the name Turing Test became popular later.",
            "CONTRADICTED",
        ),
        (
            "Google was founded in 1998 by Larry Page and Sergey Brin.",
            "Google was founded in 1998 by Larry Page and Sergey Brin.",
            "SUPPORTED",
        ),
        (
            "Microsoft was founded in 1975 by Bill Gates and Paul Allen.",
            "Microsoft was founded in 1975 by Bill Gates and Paul Allen.",
            "SUPPORTED",
        ),
    ],
)
@pytest.mark.asyncio
@patch("app.detector.fact_check.generate_verified_correction", new_callable=AsyncMock)
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_named_factual_scenarios_with_mocked_evidence(
    mock_verify, mock_search, mock_store, mock_correction, claim, evidence, verdict
):
    mock_store.query_hybrid.return_value = [_hybrid_result(evidence)]
    mock_search.return_value = []
    mock_verify.return_value = json.dumps(
        {
            "verdict": verdict,
            "relevant_candidates": [1],
            "supporting_candidates": [1] if verdict == "SUPPORTED" else [],
            "contradicting_candidates": [1] if verdict == "CONTRADICTED" else [],
        }
    )
    mock_correction.return_value = None

    reports, _ = await fact_check_claims([claim], use_web_search=False)

    assert reports[0]["verdict"] == verdict
    assert reports[0]["evidence_items"][0]["text"] == evidence


@pytest.mark.asyncio
@patch("app.detector.fact_check.store")
@patch("app.detector.fact_check.search_web_async", new_callable=AsyncMock)
@patch("app.detector.fact_check.verify_prompt_async", new_callable=AsyncMock)
async def test_relevant_but_ambiguous_evidence_is_uncertain(
    mock_verify, mock_search, mock_store
):
    mock_store.query_hybrid.return_value = [_hybrid_result("A workshop on AI was held in 1956.")]
    mock_search.return_value = []
    mock_verify.return_value = json.dumps(
        {"verdict": "UNCERTAIN", "relevant_candidates": [1]}
    )

    reports, _ = await fact_check_claims(
        ["The workshop established all modern AI research in 1956."],
        use_web_search=False,
    )

    assert reports[0]["verdict"] == "UNCERTAIN"
    assert reports[0]["evidence_items"][0]["relation"] == "context"
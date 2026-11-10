from unittest.mock import patch

from app.detector.claims import extract_claim_details, extract_claims, extract_claims_with_status


def test_empty_answer_returns_no_claims():
    assert extract_claims("") == []
    assert extract_claims("   ") == []


def test_llm_error_answer_returns_no_claims():
    assert extract_claims("LLM Error: generation timed out") == []
    assert extract_claims_with_status("LLM Error: generation timed out").status == "provider_error"


@patch("app.detector.claims.verify_prompt")
def test_extracts_atomic_claims_and_source_metadata(mock_verify):
    source = "The Eiffel Tower was completed in 1889 and is 330 meters tall."
    mock_verify.return_value = '''
    {"claims": [
      {"text": "The Eiffel Tower was completed in 1889.", "source_text": "The Eiffel Tower was completed in 1889 and is 330 meters tall.", "category": "historical", "entities": [{"text": "Eiffel Tower", "kind": "location"}], "dates": ["1889"], "quantities": [], "relationships": [], "context_dependent": false, "is_factual": true},
      {"text": "The Eiffel Tower is 330 meters tall.", "source_text": "The Eiffel Tower was completed in 1889 and is 330 meters tall.", "category": "geographical", "entities": [{"text": "Eiffel Tower", "kind": "location"}], "dates": [], "quantities": ["330 meters"], "relationships": [], "context_dependent": false, "is_factual": true}
    ]}
    '''

    details = extract_claim_details(source)

    assert [claim.text for claim in details] == [
        "The Eiffel Tower was completed in 1889.",
        "The Eiffel Tower is 330 meters tall.",
    ]
    assert all(claim.source_text == source for claim in details)
    assert all(source[claim.start_offset:claim.end_offset] == source for claim in details)
    assert details[0].dates == ["1889"]
    assert details[1].quantities == ["330 meters"]
    assert extract_claims(source) == [claim.text for claim in details]


@patch("app.detector.claims.verify_prompt")
def test_ignores_non_factual_items_and_unmatched_source_text(mock_verify):
    mock_verify.return_value = '''
    {"claims": [
      {"text": "This is wonderful.", "source_text": "This is wonderful.", "is_factual": false},
      {"text": "Invented claim.", "source_text": "Not in the answer."}
    ]}
    '''

    assert extract_claim_details("This is wonderful.") == []


@patch("app.detector.claims.verify_prompt")
def test_non_factual_input_has_distinct_extraction_status(mock_verify):
    mock_verify.return_value = '{"claims": []}'

    outcome = extract_claims_with_status("Hello there, this is a nice day.")

    assert outcome.claims == []
    assert outcome.status == "no_factual_claims"


@patch("app.detector.claims.verify_prompt")
def test_source_span_mismatch_is_reported(mock_verify):
    mock_verify.return_value = (
        '{"claims": [{"text": "A factual statement.", '
        '"source_text": "A different sentence."}]}'
    )

    outcome = extract_claims_with_status("A factual statement.")

    assert outcome.claims == []
    assert outcome.status == "source_span_mismatch"


@patch("app.detector.claims.verify_prompt")
def test_blank_verifier_response_returns_no_claims(mock_verify):
    mock_verify.return_value = ""
    assert extract_claims("some answer") == []


@patch("app.detector.claims.verify_prompt")
def test_malformed_verifier_response_returns_no_claims(mock_verify):
    mock_verify.return_value = "SUPPORTED\n1. A claim that was not validated."
    assert extract_claim_details("A claim that was not validated.") == []
    assert extract_claims_with_status("A claim that was not validated.").status == "invalid_response"

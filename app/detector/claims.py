import json
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.llm.verifier import verify_prompt
from app.utils.prompt_safety import VERIFICATION_SYSTEM_INSTRUCTION, wrap_untrusted

class ExtractedEntity(BaseModel):
    text: str = Field(min_length=1)
    kind: Literal["person", "organization", "location", "other"]


class ClaimRelationship(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object: str = Field(min_length=1)


class ClaimMetadata(BaseModel):
    text: str = Field(min_length=1)
    source_text: str = Field(min_length=1)
    category: Literal[
        "historical", "geographical", "scientific", "medical", "technical", "general"
    ] = "general"
    entities: list[ExtractedEntity] = Field(default_factory=list, max_length=30)
    dates: list[str] = Field(default_factory=list, max_length=20)
    quantities: list[str] = Field(default_factory=list, max_length=20)
    relationships: list[ClaimRelationship] = Field(default_factory=list, max_length=20)
    context_dependent: bool = False
    is_factual: bool = True


class ExtractedClaim(ClaimMetadata):
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)


class ClaimExtractionResponse(BaseModel):
    claims: list[ClaimMetadata] = Field(default_factory=list, max_length=100)


@dataclass(frozen=True)
class ClaimExtractionOutcome:
    claims: list[ExtractedClaim]
    status: Literal[
        "empty_input",
        "provider_error",
        "invalid_response",
        "no_factual_claims",
        "sentence_split",
        "source_span_mismatch",
        "partial_source_span_mismatch",
        "complete",
    ]


def _parse_extraction_response(raw: str) -> ClaimExtractionResponse:
    candidate = raw.strip()
    fenced = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.IGNORECASE | re.DOTALL
    )
    if fenced:
        candidate = fenced.group(1)
    return ClaimExtractionResponse.model_validate_json(candidate)


def extract_claims_with_status(answer: str) -> ClaimExtractionOutcome:
    if not answer or not answer.strip():
        return ClaimExtractionOutcome([], "empty_input")

    if answer.startswith("LLM Error"):
        return ClaimExtractionOutcome([], "provider_error")

    prompt = f"""Extract factual claims from the supplied text.
    Split compound sentences into independent claims. Exclude opinions that
    make no verifiable factual assertion. Preserve the original meaning and
    include the exact, contiguous source sentence for every claim in
    source_text. Do not invent claims, entities, dates, values, or
    relationships. Mark context_dependent when a claim cannot be resolved
    without surrounding context. Classify each claim as historical,
    geographical, scientific, medical, technical, or general.

    Return one JSON object with this shape:
    {{"claims": [{{"text": "...", "source_text": "...", "category": "general",
    "entities": [{{"text": "...", "kind": "person"}}], "dates": [],
    "quantities": [], "relationships": [{{"subject": "...", "predicate": "...",
    "object": "..."}}], "context_dependent": false, "is_factual": true}}]}}
    Use only person, organization, location, or other for entity kind. Return
    valid JSON only. Use an empty claims array when there are no factual claims.

    Text:
    {wrap_untrusted(answer)}
    """
    result = verify_prompt(prompt, system_instruction=VERIFICATION_SYSTEM_INSTRUCTION)
    if not result or not result.strip():
        return ClaimExtractionOutcome([], "provider_error")

    try:
        parsed = _parse_extraction_response(result)
    except (ValueError, ValidationError):
        return ClaimExtractionOutcome([], "invalid_response")

    factual_metadata = [metadata for metadata in parsed.claims if metadata.is_factual]
    if not factual_metadata:
        return ClaimExtractionOutcome([], "no_factual_claims")

    extracted: list[ExtractedClaim] = []
    search_from = 0
    seen: set[tuple[str, int, int]] = set()
    for metadata in factual_metadata:
        start = answer.find(metadata.source_text, search_from)
        if start < 0:
            start = answer.find(metadata.source_text)
        if start < 0:
            continue

        end = start + len(metadata.source_text)
        identity = (metadata.text.casefold(), start, end)
        if identity in seen:
            continue
        seen.add(identity)
        extracted.append(
            ExtractedClaim(
                **metadata.model_dump(),
                start_offset=start,
                end_offset=end,
            )
        )
        search_from = max(search_from, end)

    if not extracted:
        return ClaimExtractionOutcome([], "source_span_mismatch")
    if len(extracted) < len(factual_metadata):
        return ClaimExtractionOutcome(extracted, "partial_source_span_mismatch")
    return ClaimExtractionOutcome(extracted, "complete")


def extract_claim_details(answer: str) -> list[ExtractedClaim]:
    return extract_claims_with_status(answer).claims


def extract_claims(answer: str) -> list[str]:
    """Compatibility helper returning only claim text for existing callers."""
    return [claim.text for claim in extract_claim_details(answer)]

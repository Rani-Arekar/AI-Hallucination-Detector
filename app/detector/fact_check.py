import asyncio
import json
import logging
import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, ValidationError

from app.detector.corrections import generate_verified_correction
from app.llm.verifier import verify_prompt_async
from app.utils.prompt_safety import VERIFICATION_SYSTEM_INSTRUCTION, wrap_untrusted
from app.utils.web_search import search_web_async
from app.vector_db.simple_store import store

logger = logging.getLogger(__name__)


VERDICTS = (
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "CONTRADICTED",
    "UNCERTAIN",
    "NO_RELEVANT_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
)

_VERDICT_SCORE = {
    "SUPPORTED": 1.0,
    "PARTIALLY_SUPPORTED": 0.6,
    "UNCERTAIN": 0.5,
    "CONTRADICTED": 0.0,
    "NO_RELEVANT_EVIDENCE": 0.5,
    "INSUFFICIENT_EVIDENCE": 0.5,
}


CandidateIndex = Annotated[int, Field(strict=True, ge=1, le=20)]


class VerificationAssessment(BaseModel):
    verdict: Literal[
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "CONTRADICTED",
        "UNCERTAIN",
        "NO_RELEVANT_EVIDENCE",
    ]
    relevant_candidates: list[CandidateIndex] = Field(default_factory=list, max_length=20)
    supporting_candidates: list[CandidateIndex] | None = Field(default=None, max_length=20)
    contradicting_candidates: list[CandidateIndex] | None = Field(default=None, max_length=20)


def _deduplicate_candidates(candidates: list[dict]) -> list[dict]:
    unique: list[dict] = []
    positions: dict[str, int] = {}
    for candidate in candidates:
        key = re.sub(r"\W+", " ", candidate["content"].casefold()).strip()
        if not key:
            continue
        existing_index = positions.get(key)
        if existing_index is None:
            positions[key] = len(unique)
            unique.append(candidate)
            continue

        existing = unique[existing_index]
        if candidate.get("url") and not existing.get("url"):
            candidate["semantic_similarity"] = candidate.get("semantic_similarity") or existing.get("semantic_similarity")
            candidate["retrieval_score"] = max(
                candidate.get("retrieval_score", 0), existing.get("retrieval_score", 0)
            )
            unique[existing_index] = candidate
    return unique


def _contextual_query(claim: str, context: dict | None) -> str:
    context = context or {}
    parts = [claim]
    source_text = context.get("source_text")
    if isinstance(source_text, str) and source_text.strip():
        parts.append(source_text.strip())
    for field in ("entities", "dates", "quantities"):
        for value in context.get(field, []):
            text = value.get("text") if isinstance(value, dict) else value
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    for relationship in context.get("relationships", []):
        if isinstance(relationship, dict):
            parts.extend(
                value.strip()
                for value in relationship.values()
                if isinstance(value, str) and value.strip()
            )
    return " ".join(dict.fromkeys(parts))


def _alternative_queries(
    claim: str, context: dict | None, primary_query: str
) -> list[str]:
    context = context or {}
    entity_terms = []
    for field in ("entities", "dates", "quantities"):
        for value in context.get(field, []):
            text = value.get("text") if isinstance(value, dict) else value
            if isinstance(text, str) and text.strip():
                entity_terms.append(text.strip())
    relationship_terms = []
    for relationship in context.get("relationships", []):
        if isinstance(relationship, dict):
            relationship_terms.extend(
                value.strip()
                for value in relationship.values()
                if isinstance(value, str) and value.strip()
            )
    source_text = context.get("source_text")
    contextual_terms = [
        source_text.strip() if isinstance(source_text, str) else "",
        *relationship_terms,
        claim.strip(),
    ]
    candidates = [
        " ".join(dict.fromkeys([*entity_terms, claim.strip()])),
        " ".join(dict.fromkeys(term for term in contextual_terms if term)),
    ]
    alternatives = []
    seen = {primary_query.casefold()}
    for candidate in candidates:
        normalized = candidate.strip()
        if normalized and normalized.casefold() not in seen:
            seen.add(normalized.casefold())
            alternatives.append(normalized)
    return alternatives


def _web_candidate(result: dict) -> dict | None:
    body = result.get("body")
    if not isinstance(body, str) or not body.strip():
        return None
    return {
        "content": body,
        "source": result.get("evidence_type", "SEARCH_RESULT_SNIPPET"),
        "title": result.get("title", ""),
        "url": result.get("url", ""),
        "retrieved_at": result.get("retrieved_at"),
        "published_at": result.get("published_at"),
        "author": result.get("author"),
        "publisher": result.get("publisher"),
        "semantic_similarity": None,
        "keyword_score": 0.0,
        "retrieval_score": 0.0,
    }


def _verification_prompt(claim: str, context: dict | None, candidates: list[dict]) -> str:
    evidence_parts = []
    for index, candidate in enumerate(candidates, start=1):
        if candidate["source"] == "LOCAL KNOWLEDGE BASE":
            evidence_parts.append(
                f"""[CANDIDATE {index}]
        LOCAL KNOWLEDGE BASE
        Content: {candidate["content"]}"""
            )
        else:
            evidence_parts.append(
                f"""[CANDIDATE {index}]
        {candidate['source']}
        Title: {candidate["title"]}
        Publisher: {candidate.get("publisher") or "Unavailable"}
        Author: {candidate.get("author") or "Unavailable"}
        Published: {candidate.get("published_at") or "Unavailable"}
        URL: {candidate["url"]}
        Content: {candidate["content"]}"""
            )
    evidence_text = "\n\n".join(evidence_parts).strip()
    return f"""
Claim:
{wrap_untrusted(claim)}

Original sentence and extracted context:
{wrap_untrusted(json.dumps(context or {}, ensure_ascii=False))}

Candidate evidence:

{wrap_untrusted(evidence_text)}

Assess the candidate evidence carefully.

Determine whether at least one candidate actually addresses the claim.
Identify candidates that support the claim and candidates that contradict it
separately. If relevant evidence directly supports and contradicts the claim,
return UNCERTAIN unless the evidence itself resolves the conflict.

Use exactly one label:

SUPPORTED
- At least one candidate directly supports the claim.

PARTIALLY_SUPPORTED
- Relevant evidence supports only part of the claim or leaves an important
  part unverified.

CONTRADICTED
- Relevant evidence directly conflicts with the claim.

UNCERTAIN
- Relevant evidence addresses the claim, but it is insufficient or ambiguous
  to determine whether the claim is true.

NO_RELEVANT_EVIDENCE
- Candidate material exists, but none of it actually addresses the claim.
- Do not treat merely similar words or unrelated facts as relevant evidence.

Important:
- Do not infer support from the topic alone.
- Do not treat unrelated local knowledge-base documents as evidence.
- Consider publisher, author, and publication date only when provided; do not
    infer credibility from a domain suffix alone.
- Evaluate the actual content of each candidate.
Return valid JSON only, using exactly this structure:

{{
  "verdict": "SUPPORTED",
    "relevant_candidates": [1],
    "supporting_candidates": [1],
    "contradicting_candidates": []
}}

Rules:
- "verdict" must be exactly one of:
  SUPPORTED
  PARTIALLY_SUPPORTED
  CONTRADICTED
  UNCERTAIN
  NO_RELEVANT_EVIDENCE
- "relevant_candidates" must contain the 1-based candidate numbers
  that actually address the claim.
- "supporting_candidates" and "contradicting_candidates" must identify the
    relevant candidates on each side. A candidate must not appear on both sides.
- "relevant_candidates" must be the union of the two directional lists.
- Include only candidates that are relevant to the claim.
- If no candidate is relevant, return an empty list.
- Return JSON only. No markdown or explanation.
"""


def _parse_verdict(raw: str) -> str:
    normalized = (raw or "").strip().upper()
    return normalized if normalized in VERDICTS else "UNCERTAIN"


def _parse_verification_response(
    raw: str,
) -> tuple[str, list[int], list[int], list[int], bool]:
    try:
        data = json.loads(raw)
        assessment = VerificationAssessment.model_validate(data)
        if (
            assessment.supporting_candidates is None
            and assessment.contradicting_candidates is None
        ):
            relevant = assessment.relevant_candidates
            supporting = (
                relevant
                if assessment.verdict in {"SUPPORTED", "PARTIALLY_SUPPORTED"}
                else []
            )
            contradicting = relevant if assessment.verdict == "CONTRADICTED" else []
        else:
            supporting = assessment.supporting_candidates or []
            contradicting = assessment.contradicting_candidates or []
            relevant = sorted(set(supporting + contradicting))
            if set(relevant) != set(assessment.relevant_candidates):
                return "UNCERTAIN", [], [], [], False
        verdict = assessment.verdict
        if (
            (supporting and contradicting)
            or (verdict == "SUPPORTED" and contradicting and not supporting)
            or (verdict == "CONTRADICTED" and supporting and not contradicting)
            or (verdict == "NO_RELEVANT_EVIDENCE" and relevant)
        ):
            verdict = "UNCERTAIN"
        return verdict, relevant, supporting, contradicting, True
    except (json.JSONDecodeError, TypeError, ValidationError, ValueError):
        return "UNCERTAIN", [], [], [], False
    
async def _verify_one_claim(
    claim: str,
    semaphore: asyncio.Semaphore,
    use_web_search: bool,
    use_knowledge_base: bool,
    context: dict | None = None,
) -> dict:
    async with semaphore:
        retrieval_query = _contextual_query(claim, context)

        async def kb_lookup():
            if not use_knowledge_base:
                return []
            try:
                return await asyncio.to_thread(store.query_hybrid, retrieval_query, 5)
            except Exception as e:
                logger.warning("KB lookup failed (%s)", type(e).__name__)
                return []

        async def web_lookup():
            if not use_web_search:
                return []
            try:
                results = await search_web_async(retrieval_query)
                if results:
                    return results
                for alternative in _alternative_queries(claim, context, retrieval_query):
                    results = await search_web_async(alternative)
                    if results:
                        return results
                return []
            except Exception as e:
                logger.warning("Web search failed (%s)", type(e).__name__)
                return []

        kb_docs, web_results = await asyncio.gather(
            kb_lookup(),
            web_lookup(),
        )

        # No retrieval results at all.
        if not kb_docs and not web_results:
            return {
                "claim": claim,
                "verdict": "INSUFFICIENT_EVIDENCE",
                "score": _VERDICT_SCORE["INSUFFICIENT_EVIDENCE"],
                "evidence": None,
                "sources": [],
                "evidence_items": [],
                "verification_reasoning": "No local or web evidence was available.",
                "evidence_availability": "none",
            }

        # Keep local KB and web results clearly separated.
        candidates = []
        sources = []

        for item in kb_docs:
            candidates.append(
                {
                    "content": item["text"],
                    "source": "LOCAL KNOWLEDGE BASE",
                    "title": None,
                    "url": None,
                    "retrieved_at": None,
                    "published_at": None,
                    "author": None,
                    "publisher": None,
                    "semantic_similarity": item.get("semantic_similarity"),
                    "keyword_score": item.get("keyword_score", 0.0),
                    "retrieval_score": item.get("retrieval_score", 0.0),
                }
            )

        candidates.extend(
            candidate
            for result in web_results
            if (candidate := _web_candidate(result)) is not None
        )

        candidates = _deduplicate_candidates(candidates)
        if not candidates:
            return {
                "claim": claim,
                "verdict": "INSUFFICIENT_EVIDENCE",
                "score": _VERDICT_SCORE["INSUFFICIENT_EVIDENCE"],
                "evidence": None,
                "sources": [],
                "evidence_items": [],
                "verification_reasoning": "Retrieved candidates contained no usable evidence.",
                "evidence_availability": "none",
            }

        alternatives = iter(_alternative_queries(claim, context, retrieval_query))
        retry_count = 0
        while True:
            prompt = _verification_prompt(claim, context, candidates)
            try:
                raw_verdict = await verify_prompt_async(
                    prompt,
                    system_instruction=VERIFICATION_SYSTEM_INSTRUCTION,
                )
            except Exception as e:
                logger.warning("Verifier call failed (%s)", type(e).__name__)
                raw_verdict = ""

            (
                verdict,
                relevant_candidates,
                supporting_candidates,
                contradicting_candidates,
                valid_response,
            ) = _parse_verification_response(raw_verdict)

            if not valid_response:
                return {
                    "claim": claim,
                    "verdict": "UNCERTAIN",
                    "score": _VERDICT_SCORE["UNCERTAIN"],
                    "evidence": None,
                    "sources": [],
                    "evidence_items": [],
                    "verification_reasoning": (
                        "Verification was unavailable or returned invalid structured output; "
                        "retrieved material was not accepted as support."
                    ),
                    "evidence_availability": "verification_unavailable",
                }

            candidate_indexes = set(
                relevant_candidates + supporting_candidates + contradicting_candidates
            )
            if any(index > len(candidates) for index in candidate_indexes):
                return {
                    "claim": claim,
                    "verdict": "UNCERTAIN",
                    "score": _VERDICT_SCORE["UNCERTAIN"],
                    "evidence": None,
                    "sources": [],
                    "evidence_items": [],
                    "verification_reasoning": (
                        "Verification returned a candidate index outside the retrieved evidence set."
                    ),
                    "evidence_availability": "verification_unavailable",
                }

            if verdict != "NO_RELEVANT_EVIDENCE" or not use_web_search or retry_count >= 2:
                break

            added_candidates = False
            while retry_count < 2:
                alternative = next(alternatives, None)
                if alternative is None:
                    break
                retry_count += 1
                try:
                    alternative_results = await search_web_async(alternative)
                except Exception as e:
                    logger.warning("Alternative web search failed (%s)", type(e).__name__)
                    continue
                previous_count = len(candidates)
                candidates = _deduplicate_candidates(
                    candidates
                    + [
                        candidate
                        for result in alternative_results
                        if (candidate := _web_candidate(result)) is not None
                    ]
                )
                if len(candidates) > previous_count:
                    added_candidates = True
                    break
            if not added_candidates:
                break

        if (
            (supporting_candidates and contradicting_candidates)
            or (verdict == "SUPPORTED" and contradicting_candidates and not supporting_candidates)
            or (verdict == "CONTRADICTED" and supporting_candidates and not contradicting_candidates)
            or (verdict == "NO_RELEVANT_EVIDENCE" and relevant_candidates)
        ):
            verdict = "UNCERTAIN"

        if verdict == "NO_RELEVANT_EVIDENCE" or not relevant_candidates:
            return {
                "claim": claim,
                "verdict": verdict,
                "score": _VERDICT_SCORE[verdict],
                "evidence": None,
                "sources": [],
                "evidence_items": [],
                "verification_reasoning": "Retrieved candidates were not relevant to the claim.",
                "evidence_availability": "irrelevant",
            }

        selected_candidates = [
            candidates[index - 1]
            for index in relevant_candidates
            if 1 <= index <= len(candidates)
        ]

        if not selected_candidates:
            return {
                "claim": claim,
                "verdict": "NO_RELEVANT_EVIDENCE",
                "score": _VERDICT_SCORE["NO_RELEVANT_EVIDENCE"],
                "evidence": None,
                "sources": [],
                "evidence_items": [],
                "verification_reasoning": "The verifier found no relevant candidate evidence.",
                "evidence_availability": "irrelevant",
            }

        selected_evidence = "\n\n".join(
            candidate["content"]
            for candidate in selected_candidates
        )

        selected_sources = [
            {
                "title": candidate["title"],
                "url": candidate["url"],
            }
            for candidate in selected_candidates
            if candidate["url"]
        ]

        supporting_set = set(supporting_candidates)
        contradicting_set = set(contradicting_candidates)
        evidence_items = []
        for index, candidate in enumerate(candidates, start=1):
            if index not in relevant_candidates:
                continue
            relation = (
                "context" if index in supporting_set and index in contradicting_set
                else "supports" if index in supporting_set
                else "contradicts" if index in contradicting_set
                else "context"
            )
            evidence_items.append({
                "text": candidate["content"][:800],
                "source_type": candidate["source"],
                "title": candidate["title"],
                "url": candidate["url"],
                "retrieved_at": candidate["retrieved_at"],
                "published_at": candidate["published_at"],
                "author": candidate["author"],
                "publisher": candidate["publisher"],
                "semantic_similarity": candidate["semantic_similarity"],
                "keyword_score": candidate.get("keyword_score", 0.0),
                "retrieval_score": candidate.get("retrieval_score", 0.0),
                "relation": relation,
            })

        correction = None
        if verdict == "CONTRADICTED" and contradicting_candidates:
            correction_sources = [
                candidates[index - 1]
                for index in contradicting_candidates
                if 1 <= index <= len(candidates)
            ]
            correction = await generate_verified_correction(claim, correction_sources)

        return {
            "claim": claim,
            "verdict": verdict,
            "score": _VERDICT_SCORE[verdict],
            "evidence": selected_evidence[:800],
            "sources": selected_sources,
            "evidence_items": evidence_items,
            "suggested_correction": correction,
            "verification_reasoning": (
                f"The verifier classified the claim as {verdict.replace('_', ' ').lower()} "
                f"using {len(selected_candidates)} relevant evidence item(s)."
            ),
            "evidence_availability": "available",
        }

async def fact_check_claims(
    claims: list[str],
    max_concurrent: int = 5,
    use_web_search: bool = True,
    use_knowledge_base: bool = True,
    claim_contexts: list[dict] | None = None,
) -> tuple[list[dict], float]:
    if not claims:
        return [], 1.0

    semaphore = asyncio.Semaphore(max_concurrent)
    raw_results = await asyncio.gather(
        *[
            _verify_one_claim(
                claim,
                semaphore,
                use_web_search,
                use_knowledge_base,
                claim_contexts[index] if claim_contexts and index < len(claim_contexts) else None,
            )
            for index, claim in enumerate(claims)
        ],
        return_exceptions=True,
    )

    results = []
    for claim, r in zip(claims, raw_results):
        if isinstance(r, Exception):
            logger.error("Unexpected claim verification failure (%s)", type(r).__name__)
            results.append(
                {
                    "claim": claim,
                    "verdict": "UNCERTAIN",
                    "score": _VERDICT_SCORE["UNCERTAIN"],
                    "evidence": None,
                    "sources": [],
                    "error": str(r),
                }
            )
        else:
            results.append(r)

    avg_score = sum(r["score"] for r in results) / len(results)
    return results, avg_score

import json
import logging
from typing import Annotated, Literal

from pydantic import BaseModel, Field, ValidationError

from app.llm.verifier import verify_prompt_async
from app.utils.prompt_safety import VERIFICATION_SYSTEM_INSTRUCTION, wrap_untrusted

logger = logging.getLogger(__name__)
CandidateIndex = Annotated[int, Field(strict=True, ge=1, le=20)]


class CorrectionProposal(BaseModel):
    correction: str = Field(min_length=1, max_length=2000)
    evidence_candidates: list[CandidateIndex] = Field(min_length=1, max_length=20)


class CorrectionAssessment(BaseModel):
    verdict: Literal["SUPPORTED", "CONTRADICTED", "UNCERTAIN", "UNVERIFIABLE"]
    supporting_candidates: list[CandidateIndex] = Field(default_factory=list, max_length=20)


async def generate_verified_correction(claim: str, evidence: list[dict]) -> dict | None:
    """Return a correction only when selected evidence supports it on recheck."""
    if not evidence:
        return None

    evidence_text = "\n\n".join(
        f"[EVIDENCE {index}]\nTitle: {item.get('title') or 'Unknown'}\n"
        f"URL: {item.get('url') or 'Unavailable'}\n"
        f"Text: {item.get('text') or item.get('content', '')}"
        for index, item in enumerate(evidence, start=1)
    )
    proposal_prompt = f"""Propose a minimal factual correction to the claim using only the supplied evidence.
If the evidence does not establish a safe correction, return {{"correction":"","evidence_candidates":[]}}.
Return valid JSON only with fields correction and evidence_candidates, where the latter
contains 1-based evidence indexes that directly support the correction.

Original claim:
{wrap_untrusted(claim)}

Evidence:
{wrap_untrusted(evidence_text)}
"""
    try:
        proposal_raw = await verify_prompt_async(
            proposal_prompt, system_instruction=VERIFICATION_SYSTEM_INSTRUCTION
        )
        proposal = CorrectionProposal.model_validate(json.loads(proposal_raw))
        if any(index > len(evidence) for index in proposal.evidence_candidates):
            return None
        if proposal.correction.strip().casefold() == claim.strip().casefold():
            return None

        selected = [evidence[index - 1] for index in proposal.evidence_candidates]
        selected_text = "\n\n".join(
            f"[EVIDENCE {index}]\n{item.get('text') or item.get('content', '')}"
            for index, item in enumerate(selected, start=1)
        )
        verification_prompt = f"""Verify whether the proposed correction is directly supported by the supplied evidence.
Return valid JSON only with fields verdict and supporting_candidates. The verdict must be
SUPPORTED, CONTRADICTED, UNCERTAIN, or UNVERIFIABLE. supporting_candidates must contain
1-based indexes of evidence that directly supports the correction.

Proposed correction:
{wrap_untrusted(proposal.correction)}

Evidence:
{wrap_untrusted(selected_text)}
"""
        verification_raw = await verify_prompt_async(
            verification_prompt, system_instruction=VERIFICATION_SYSTEM_INSTRUCTION
        )
        assessment = CorrectionAssessment.model_validate(json.loads(verification_raw))
        if assessment.verdict != "SUPPORTED" or not assessment.supporting_candidates:
            return None
        if any(index > len(selected) for index in assessment.supporting_candidates):
            return None

        verified_evidence = [
            {
                "text": selected[index - 1].get("text") or selected[index - 1].get("content", ""),
                "title": selected[index - 1].get("title"),
                "url": selected[index - 1].get("url"),
                "retrieved_at": selected[index - 1].get("retrieved_at"),
                "published_at": selected[index - 1].get("published_at"),
                "author": selected[index - 1].get("author"),
                "publisher": selected[index - 1].get("publisher"),
                "source_type": selected[index - 1].get("source_type"),
                "semantic_similarity": selected[index - 1].get("semantic_similarity"),
                "retrieval_score": selected[index - 1].get("retrieval_score"),
                "relation": "supports",
            }
            for index in assessment.supporting_candidates
        ]
        return {
            "text": proposal.correction.strip(),
            "explanation": "The displayed evidence was checked against this suggested wording.",
            "evidence": verified_evidence,
        }
    except (json.JSONDecodeError, TypeError, ValidationError, ValueError) as error:
        logger.info("Correction response was invalid: %s", error)
        return None
    except Exception:
        logger.warning("Suggested correction verification failed", exc_info=True)
        return None
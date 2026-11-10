import asyncio
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi import Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import (
    ALLOWED_ORIGINS,
    MAX_REQUEST_BODY_BYTES,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    GEMINI_API_KEY,
)
from app.detector.pipeline import run_detection
from app.llm.generator import generate_answer_async
from app.schemas.response_schema import (
    AnalyzeRequest,
    AnalysisResponse,
    PublicAnalysisResponse,
    PublicClaim,
    PublicEvidence,
    AnalyticsResponse,
    HistoryRecordResponse,
    Query,
)
from app.utils.rate_limit import SlidingWindowRateLimiter
from app.vector_db.load_kb import load_default_kb
from app.history import analytics as get_analytics, delete_analyses, get_analysis, list_analyses, save_analysis
from app.db import init_db
from app.config import HISTORY_AUTH_REQUIRED

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_default_kb()
init_db()

app = FastAPI(title="AI Hallucination Detector", version="0.3.0")

# CORS: restricted to ALLOWED_ORIGINS (see app/config.py), not a wildcard.
# Set ALLOWED_ORIGINS in the deployment environment to the real deployed
# frontend URL (e.g. Vercel/Netlify).
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

_rate_limiter = SlidingWindowRateLimiter(
    max_requests=RATE_LIMIT_REQUESTS, window_seconds=RATE_LIMIT_WINDOW_SECONDS
)


def _client_key(request: Request) -> str:
    # Render sits behind a proxy; prefer the forwarded client IP when present.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def request_guards(request: Request, call_next):
    """Applies, in order: request-size limit, rate limiting, and an overall
    request timeout. Kept as one middleware so the ordering (cheapest check
    first) is explicit and easy to audit.
    """
    # 1. Reject oversized bodies before they're read into memory.
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"error": "request body too large"},
                )
        except ValueError:
            pass  # malformed header; let normal parsing surface the problem

    # 2. Rate limit per client, only on the actual analysis endpoint --
    # health checks and docs shouldn't count against the budget.
    if request.url.path in ("/ask", "/api/analyze"):
        client_key = _client_key(request)
        allowed, retry_after = _rate_limiter.check(client_key)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "rate limit exceeded, please slow down"},
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

    # 3. Overall timeout so a hang anywhere (including something not
    # covered by the per-call timeouts deeper in the pipeline) can't hold a
    # worker forever.
    try:
        return await asyncio.wait_for(call_next(request), timeout=REQUEST_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("Request to %s timed out after %.0fs", request.url.path, REQUEST_TIMEOUT_SECONDS)
        return JSONResponse(status_code=504, content={"error": "request timed out"})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Full detail goes to the server log only -- never back to the client.
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": "internal server error"})


@app.post("/ask")
async def ask(q: Query):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Gemini API credentials are not configured")
    request_start = time.perf_counter()

    gen_start = time.perf_counter()
    answer = await generate_answer_async(q.prompt)
    generation_ms = (time.perf_counter() - gen_start) * 1000

    report = await run_detection(q.prompt, answer, mode=q.mode)

    report["latency"]["generation_ms"] = round(generation_ms, 1)
    report["latency"]["total_ms"] = round((time.perf_counter() - request_start) * 1000, 1)

    return {"answer": answer, **report}


def _public_status(verdict: str) -> str:
    return {
        "SUPPORTED": "supported",
        "CONTRADICTED": "contradicted",
        "UNCERTAIN": "uncertain",
        "PARTIALLY_SUPPORTED": "uncertain",
        "NO_RELEVANT_EVIDENCE": "unverifiable",
        "INSUFFICIENT_EVIDENCE": "unverifiable",
    }.get(verdict, "unverifiable")


def _public_claim(report: dict, analysis_id: str, index: int) -> PublicClaim:
    status = _public_status(report.get("verdict", "UNVERIFIABLE"))
    evidence: list[PublicEvidence] = []
    for item in report.get("supporting_evidence", []):
        evidence.append(
            PublicEvidence(
                text=item["text"],
                url=item.get("url"),
                title=item.get("title"),
                sourceType=item.get("source_type"),
                retrievedAt=item.get("retrieved_at"),
                publishedAt=item.get("published_at"),
                author=item.get("author"),
                publisher=item.get("publisher"),
                semanticSimilarity=item.get("semantic_similarity"),
                retrievalScore=item.get("retrieval_score"),
                relation=item.get("relation", "supports" if status == "supported" else "context"),
            )
        )
    for item in report.get("contradicting_evidence", []):
        evidence.append(
            PublicEvidence(
                text=item["text"],
                url=item.get("url"),
                title=item.get("title"),
                sourceType=item.get("source_type"),
                retrievedAt=item.get("retrieved_at"),
                publishedAt=item.get("published_at"),
                author=item.get("author"),
                publisher=item.get("publisher"),
                semanticSimilarity=item.get("semantic_similarity"),
                retrievalScore=item.get("retrieval_score"),
                relation="contradicts",
            )
        )
    for item in report.get("context_evidence", []):
        evidence.append(
            PublicEvidence(
                text=item["text"],
                url=item.get("url"),
                title=item.get("title"),
                sourceType=item.get("source_type"),
                retrievedAt=item.get("retrieved_at"),
                publishedAt=item.get("published_at"),
                author=item.get("author"),
                publisher=item.get("publisher"),
                semanticSimilarity=item.get("semantic_similarity"),
                retrievalScore=item.get("retrieval_score"),
                relation="context",
            )
        )
    correction_evidence = [
        PublicEvidence(
            text=item["text"],
            url=item.get("url"),
            title=item.get("title"),
            sourceType=item.get("source_type"),
            retrievedAt=item.get("retrieved_at"),
            publishedAt=item.get("published_at"),
            author=item.get("author"),
            publisher=item.get("publisher"),
            semanticSimilarity=item.get("semantic_similarity"),
            retrievalScore=item.get("retrieval_score"),
            relation="supports",
        )
        for item in report.get("correction_evidence", [])
    ]
    return PublicClaim(
        id=f"{analysis_id}-claim-{index:03d}",
        text=report["claim"],
        status=status,
        hallucinationRiskScore=report["hallucination_risk"],
        decisionConfidence=report["decision_confidence"],
        explanation=report["verification_reasoning"],
        evidence=evidence,
        evidenceAvailability=report.get("evidence_availability"),
        sourceText=report.get("source_text"),
        startOffset=report.get("start_offset"),
        endOffset=report.get("end_offset"),
        claimType=report.get("category"),
        entities=report.get("entities", []),
        dates=report.get("dates", []),
        quantities=report.get("quantities", []),
        relationships=report.get("relationships", []),
        contextDependent=report.get("context_dependent", False),
        suggestedCorrection=report.get("suggested_correction"),
        correctionExplanation=report.get("correction_explanation"),
        correctionEvidence=correction_evidence,
    )


def _owner_id(x_user_id: str | None) -> str:
    if HISTORY_AUTH_REQUIRED and not x_user_id:
        raise HTTPException(status_code=401, detail="authenticated user identity required")
    return x_user_id or "local-user"


def _history_claims(record) -> list[PublicClaim]:
    return [PublicClaim.model_validate(claim) for claim in record.claims]


def _history_record(record) -> HistoryRecordResponse:
    claims = _history_claims(record)
    total_claims = len(claims)
    resolved = record.supported_claims + record.contradicted_claims
    retrieved = sum(bool(claim.evidence) for claim in claims)
    return HistoryRecordResponse(
        id=record.id,
        title=record.title,
        preview=record.preview,
        reliabilityScore=record.reliability_score,
        hallucinationProbability=record.hallucination_risk_score,
        totalClaims=record.total_claims,
        supportedClaims=record.supported_claims,
        uncertainClaims=record.uncertain_claims,
        contradictedClaims=record.contradicted_claims,
        unverifiableClaims=record.unverifiable_claims,
        status=record.status,
        createdAt=record.created_at.isoformat(),
        sourceType=record.source_type,
        verificationMode=record.verification_mode,
        originalResponse=record.original_input or "",
        inputSaved=record.original_input is not None,
        claims=claims,
        evidenceCoverage=round(100 * resolved / total_claims) if total_claims else 0,
        retrievedEvidenceCoverage=round(100 * retrieved / total_claims) if total_claims else 0,
        resolvedReliabilityScore=(
            round(100 * record.supported_claims / resolved) if resolved else None
        ),
        resolvedClaimCount=resolved,
        contradictionRate=(
            round(100 * record.contradicted_claims / total_claims) if total_claims else 0
        ),
    )


@app.post("/api/analyze", response_model=PublicAnalysisResponse)
async def analyze(q: AnalyzeRequest, x_user_id: str | None = Header(default=None)):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Gemini API credentials are not configured")
    request_start = time.perf_counter()
    report = await run_detection(
        q.text,
        q.text,
        mode=q.mode,
        evidence_source=q.evidence_source,
        claim_granularity=q.claim_granularity,
    )
    report["latency"]["total_ms"] = round(
        (time.perf_counter() - request_start) * 1000, 1
    )
    analysis_id = f"analysis-{uuid4().hex}"
    claims = [
        _public_claim(report, analysis_id, index)
        for index, report in enumerate(report["claims"], start=1)
    ]
    response = PublicAnalysisResponse(
        analysisId=analysis_id,
        reliabilityScore=report["overall_reliability"],
        hallucinationRiskScore=report["overall_hallucination_risk"],
        decisionConfidence=report["overall_decision_confidence"],
        claimExtractionStatus=report.get("claim_extraction_status", "complete"),
        totalClaims=len(claims),
        supportedClaims=sum(claim.status == "supported" for claim in claims),
        contradictedClaims=sum(claim.status == "contradicted" for claim in claims),
        uncertainClaims=sum(claim.status == "uncertain" for claim in claims),
        unverifiableClaims=sum(claim.status == "unverifiable" for claim in claims),
        evidenceCoverage=report.get("evidence_coverage", 0),
        supportedClaimPercentage=report.get("supported_claim_percentage", 0),
        contradictedClaimPercentage=report.get("contradicted_claim_percentage", 0),
        uncertainClaimPercentage=report.get("uncertain_claim_percentage", 0),
        unverifiableClaimPercentage=report.get("unverifiable_claim_percentage", 0),
        retrievedEvidenceCoverage=report.get("retrieved_evidence_coverage", 0),
        resolvedReliabilityScore=report.get("resolved_reliability"),
        resolvedClaimCount=report.get("resolved_claim_count", 0),
        contradictionRate=report.get("contradiction_rate", 0),
        claims=claims,
    )
    if q.save_history:
        save_analysis(
            _owner_id(x_user_id),
            q.text,
            response.model_dump(),
            q.mode,
            q.evidence_source,
            q.save_input_text,
        )
    return response


@app.get("/api/history", response_model=list[HistoryRecordResponse])
def history_list(x_user_id: str | None = Header(default=None)):
    return [_history_record(record) for record in list_analyses(_owner_id(x_user_id))]


@app.get("/api/history/{analysis_id}", response_model=HistoryRecordResponse)
def history_detail(analysis_id: str, x_user_id: str | None = Header(default=None)):
    record = get_analysis(_owner_id(x_user_id), analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail="analysis not found")
    return _history_record(record)


@app.delete("/api/history/{analysis_id}", status_code=204)
def history_delete(analysis_id: str, x_user_id: str | None = Header(default=None)):
    owner_id = _owner_id(x_user_id)
    if not get_analysis(owner_id, analysis_id):
        raise HTTPException(status_code=404, detail="analysis not found")
    delete_analyses(owner_id, [analysis_id])


@app.post("/api/history/delete", response_model=list[HistoryRecordResponse])
def history_delete_many(ids: list[str], x_user_id: str | None = Header(default=None)):
    owner_id = _owner_id(x_user_id)
    delete_analyses(owner_id, ids)
    return [_history_record(record) for record in list_analyses(owner_id)]


@app.get("/api/analytics", response_model=AnalyticsResponse)
def analytics_endpoint(days: int | None = None, x_user_id: str | None = Header(default=None)):
    if days is not None and days not in (7, 30, 90, 180):
        raise HTTPException(status_code=422, detail="days must be one of 7, 30, 90, or 180")
    result = get_analytics(_owner_id(x_user_id), days)
    return AnalyticsResponse(
        totalAnalyses=result["totalAnalyses"],
        averageReliability=result["averageReliability"],
        hallucinationRate=result["hallucinationRate"],
        claimsVerified=result["claimsVerified"],
        reliabilityTrend=result["reliabilityTrend"],
        claimBreakdown=result["claimBreakdown"],
        records=[_history_record(record) for record in result["records"]],
    )


@app.get("/health")
def health():
    from app.utils.embeddings import cache_stats as embedding_cache_stats
    from app.utils.web_search import cache_stats as web_cache_stats
    from app.vector_db.simple_store import store

    return {
        "status": "ok",
        "gemini_configured": bool(GEMINI_API_KEY),
        "kb_documents": len(store.docs),
        "embedding_cache": embedding_cache_stats(),
        "web_search_cache": web_cache_stats(),
    }

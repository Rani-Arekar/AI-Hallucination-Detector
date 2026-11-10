// These types mirror the backend's actual response shape. Verified against:
//   app/detector/pipeline.py (top-level report shape + latency keys)
//   app/detector/fact_check.py (claim verdict/score/evidence/sources shape)
//   app/detector/citation_check.py (citation type/verdict shape)
//   app/schemas/response_schema.py (request shape + mode values)
// Nothing here is invented -- if the backend doesn't return a field, it's
// not in these types, and the UI must not pretend otherwise.

export type AnalysisMode = "quick" | "standard" | "deep"

export type ClaimVerdict =
  | "SUPPORTED"
  | "PARTIALLY_SUPPORTED"
  | "CONTRADICTED"
  | "UNCERTAIN"
  | "INSUFFICIENT_EVIDENCE"
  | "NO_RELEVANT_EVIDENCE"

export type CitationVerdict = "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNSUPPORTED" | "NO_SOURCE"

export type CitationType = "url" | "numbered" | "author_year"

export interface Source {
  title: string
  url: string
}

export interface ClaimReport {
  claim: string
  verdict: ClaimVerdict
  score: number
  evidence: string | null
  sources: Source[]
  error?: string
}

export interface CitationReport {
  type: CitationType
  text: string
  verdict: CitationVerdict
}

export interface ModuleScores {
  fact: number
  logic: number
  citation: number
  confidence: number
  cross: number
}

// Keys present depend on mode -- logic_ms/cross_model_ms are ABSENT
// (not zero) in Quick mode since those stages are skipped entirely.
// Everything here is optional to reflect that honestly.
export interface Latency {
  total_ms?: number
  generation_ms?: number
  claim_extraction_ms?: number
  confidence_ms?: number
  evidence_and_verification_ms?: number
  citation_ms?: number
  scoring_ms?: number
  logic_ms?: number
  cross_model_ms?: number
}

export interface AnalysisResponse {
  answer: string
  risk_score: number
  module_scores: ModuleScores
  claims: ClaimReport[]
  citations: CitationReport[]
  mode: AnalysisMode
  latency: Latency
}

export interface CacheStats {
  size: number
  maxsize: number
  hits: number
  misses: number
  hit_rate: number
}

export interface HealthResponse {
  status: string
  kb_documents: number
  embedding_cache: CacheStats
  web_search_cache: CacheStats
}

// Discriminated error info the API client normalizes backend error shapes
// into, so components never need to know which endpoint failed how.
export type ApiErrorKind =
  | "network" // couldn't reach the backend at all (or a CORS rejection -- browsers make these indistinguishable to JS)
  | "timeout" // client-side fetch timeout
  | "validation" // 422
  | "rate_limited" // 429
  | "payload_too_large" // 413
  | "not_found" // 404
  | "server_timeout" // 504
  | "server_error" // 500
  | "unknown"

export class ApiError extends Error {
  kind: ApiErrorKind
  status?: number
  retryAfterSeconds?: number

  constructor(kind: ApiErrorKind, message: string, status?: number, retryAfterSeconds?: number) {
    super(message)
    this.kind = kind
    this.status = status
    this.retryAfterSeconds = retryAfterSeconds
  }
}

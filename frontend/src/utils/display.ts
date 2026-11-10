import type { ClaimVerdict, CitationVerdict } from "../types/detector"
import type { MarkerTone } from "../components/StatusMarker"

export const claimVerdictDisplay: Record<ClaimVerdict, { label:string; tone: MarkerTone }> = {
  SUPPORTED: { label: "Supported", tone: "verify" },
  PARTIALLY_SUPPORTED: { label: "Partially supported", tone: "caution" },
  CONTRADICTED: { label: "Contradicted", tone: "risk" },
  UNCERTAIN: { label: "Uncertain", tone: "caution" },
  INSUFFICIENT_EVIDENCE: { label: "Insufficient evidence", tone: "neutral" },
  NO_RELEVANT_EVIDENCE: { label: "No relevant evidence", tone: "neutral" },
}

export const citationVerdictDisplay: Record<CitationVerdict, { label: string; tone: MarkerTone }> = {
  SUPPORTED: { label: "Source reachable", tone: "verify" },
  PARTIALLY_SUPPORTED: { label: "Source inconclusive", tone: "caution" },
  UNSUPPORTED: { label: "Source unreachable", tone: "risk" },
  NO_SOURCE: { label: "No resolvable source", tone: "neutral" },
}

export function riskBand(riskScore: number): { label: string; tone: MarkerTone } {
  if (riskScore < 30) return { label: "Low risk", tone: "verify" }
  if (riskScore < 60) return { label: "Medium risk", tone: "caution" }
  return { label: "High risk", tone: "risk" }
}

export function formatMs(ms: number | undefined): string | null {
  if (ms === undefined) return null
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(2)} s`
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

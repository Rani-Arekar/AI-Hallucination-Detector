import { useState } from "react"
import type { ClaimReport } from "../types/detector"
import { StatusBadge } from "./StatusMarker"
import { claimVerdictDisplay, formatPercent } from "../utils/display"
import { EvidencePanel } from "./EvidencePanel"

export function ClaimCard({ claim, index }: { claim: ClaimReport; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const display = claimVerdictDisplay[claim.verdict]
  const hasEvidence = Boolean(claim.evidence) || claim.sources.length > 0

  return (
    <li className="border-b border-border py-4 last:border-b-0">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs text-ink-faint">Claim {index + 1}</p>
          <p className="mt-1 text-sm text-ink">{claim.claim}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <StatusBadge tone={display.tone} label={display.label} />
          <span className="text-xs text-ink-faint">{formatPercent(claim.score)} verifier confidence</span>
        </div>
      </div>

      {hasEvidence && (
        <button
          type="button"
          className="mt-2 text-xs text-ink-muted underline decoration-border-strong underline-offset-2 hover:text-ink"
          onClick={() => setExpanded((e) => !e)}
          aria-expanded={expanded}
        >
          {expanded ? "Hide evidence" : "Show evidence"}
        </button>
      )}

      {expanded && (
        <div className="mt-3 rounded-[4px] bg-bg p-3">
          <EvidencePanel claim={claim} />
        </div>
      )}
    </li>
  )
}

import type { ClaimReport } from "../types/detector"
import { ClaimCard } from "./ClaimCard"

export function ClaimsList({ claims }: { claims: ClaimReport[] }) {
  return (
    <section className="rounded-[6px] border border-border bg-surface p-6">
      <h2 className="font-display text-lg font-semibold">Claim-level verification</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Every factual claim extracted from the answer, checked individually against evidence.
      </p>

      {claims.length === 0 ? (
        <p className="mt-4 text-sm text-ink-faint">
          No individually verifiable factual claims were extracted from this answer.
        </p>
      ) : (
        <ul className="mt-4">
          {claims.map((claim, i) => (
            <ClaimCard key={i} claim={claim} index={i} />
          ))}
        </ul>
      )}
    </section>
  )
}

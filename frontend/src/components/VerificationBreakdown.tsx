import type { ModuleScores } from "../types/detector"
import { formatPercent } from "../utils/display"

const moduleLabels: Record<keyof ModuleScores, string> = {
  fact: "Fact verification",
  logic: "Logical consistency",
  citation: "Citation quality",
  confidence: "Confidence language",
  cross: "Self-consistency",
}

export function VerificationBreakdown({ scores }: { scores: ModuleScores }) {
  const entries = Object.entries(scores) as [keyof ModuleScores, number][]

  return (
    <section className="rounded-[6px] border border-border bg-surface p-6">
      <h2 className="font-display text-lg font-semibold">Why this result</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Signals combined into the overall risk score, each on its own 0-100% scale. Weights are heuristic, not
        statistically calibrated.
      </p>

      <div className="mt-4 space-y-3">
        {entries.map(([key, value]) => (
          <div key={key}>
            <div className="flex items-center justify-between text-sm">
              <span className="text-ink-muted">{moduleLabels[key]}</span>
              <span className="text-ink-faint">{formatPercent(value)}</span>
            </div>
            <div className="mt-1 h-1.5 w-full rounded-full bg-neutral-bg">
              <div
                className="h-1.5 rounded-full bg-ink"
                style={{ width: `${Math.round(value * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

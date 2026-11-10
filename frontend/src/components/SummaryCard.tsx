import type { AnalysisResponse } from "../types/detector"
import { RiskIndicator } from "./RiskIndicator"
import { formatMs, formatPercent } from "../utils/display"

const ATTENTION_VERDICTS = new Set(["CONTRADICTED", "UNCERTAIN", "PARTIALLY_SUPPORTED", "INSUFFICIENT_EVIDENCE"])

export function SummaryCard({ result }: { result: AnalysisResponse }) {
  const needsAttention = result.claims.filter((c) => ATTENTION_VERDICTS.has(c.verdict)).length
  const totalMs = formatMs(result.latency.total_ms)

  return (
    <section className="rounded-[6px] border border-border bg-surface p-6">
      <h2 className="font-display text-lg font-semibold">Reliability summary</h2>

      <div className="mt-4 grid grid-cols-2 gap-6 sm:grid-cols-4">
        <RiskIndicator riskScore={result.risk_score} />

        <Stat label="Confidence signal" value={formatPercent(result.module_scores.confidence)} />
        <Stat label="Claims checked" value={String(result.claims.length)} />
        <Stat label="Need attention" value={String(needsAttention)} emphasize={needsAttention > 0} />
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-border pt-4 text-xs text-ink-faint">
        <span>Mode: {result.mode}</span>
        {totalMs && <span>Analysis latency: {totalMs}</span>}
        <span>{result.citations.length} citation{result.citations.length === 1 ? "" : "s"} found in the text</span>
      </div>
    </section>
  )
}

function Stat({ label, value, emphasize }: { label: string; value: string; emphasize?: boolean }) {
  return (
    <div>
      <p className={`font-display text-2xl font-semibold ${emphasize ? "text-caution" : ""}`}>{value}</p>
      <p className="mt-0.5 text-xs text-ink-muted">{label}</p>
    </div>
  )
}

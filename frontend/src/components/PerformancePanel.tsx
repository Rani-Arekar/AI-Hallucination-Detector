import type { Latency } from "../types/detector"
import { formatMs } from "../utils/display"

const stageLabels: Record<keyof Omit<Latency, "total_ms">, string> = {
  generation_ms: "Answer generation",
  claim_extraction_ms: "Claim extraction",
  confidence_ms: "Confidence scoring",
  evidence_and_verification_ms: "Evidence retrieval + verification",
  citation_ms: "Citation checking",
  scoring_ms: "Risk scoring",
  logic_ms: "Logical consistency check",
  cross_model_ms: "Self-consistency check",
}

const stageOrder: (keyof Omit<Latency, "total_ms">)[] = [
  "generation_ms",
  "claim_extraction_ms",
  "evidence_and_verification_ms",
  "confidence_ms",
  "citation_ms",
  "logic_ms",
  "cross_model_ms",
  "scoring_ms",
]

export function PerformancePanel({ latency, mode }: { latency: Latency; mode: string }) {
  const total = formatMs(latency.total_ms)
  const stages = stageOrder.filter((key) => latency[key] !== undefined)
  const skipped = stageOrder.filter(
    (key) => latency[key] === undefined && (key === "logic_ms" || key === "cross_model_ms")
  )

  return (
    <section className="rounded-[6px] border border-border bg-surface p-6">
      <h2 className="font-display text-lg font-semibold">Analysis performance</h2>
      {total && <p className="mt-1 text-sm text-ink-muted">Total: {total}</p>}

      {stages.length > 0 && (
        <table className="mt-4 w-full text-sm">
          <tbody>
            {stages.map((key) => (
              <tr key={key} className="border-t border-border first:border-t-0">
                <td className="py-1.5 text-ink-muted">{stageLabels[key]}</td>
                <td className="py-1.5 text-right font-data text-ink">{formatMs(latency[key])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {skipped.length > 0 && (
        <p className="mt-3 text-xs text-ink-faint">
          Skipped in {mode} mode: {skipped.map((k) => stageLabels[k]).join(", ")}.
        </p>
      )}
    </section>
  )
}

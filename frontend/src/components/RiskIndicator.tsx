import { riskBand } from "../utils/display"

export function RiskIndicator({ riskScore }: { riskScore: number }) {
  const band = riskBand(riskScore)
  const colorClass = band.tone === "verify" ? "text-verify" : band.tone === "caution" ? "text-caution" : "text-risk"

  return (
    <div>
      <div className="flex items-baseline gap-3">
        <span className={`font-display text-4xl font-semibold ${colorClass}`}>{riskScore}</span>
        <span className="text-sm text-ink-faint">/ 100</span>
      </div>
      <p className={`mt-1 text-sm font-medium ${colorClass}`}>{band.label}</p>
      <p className="mt-1 text-xs text-ink-faint">
        A relative signal from heuristic weights, not a calibrated probability. See the breakdown below.
      </p>
    </div>
  )
}

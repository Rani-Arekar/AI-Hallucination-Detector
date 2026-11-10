type MarkerTone = "verify" | "risk" | "caution" | "neutral"

const shapeByTone: Record<MarkerTone, string> = {
  verify: "rounded-full",
  risk: "rounded-none",
  caution: "rounded-[2px] rotate-45",
  neutral: "rounded-full",
}

const colorByTone: Record<MarkerTone, string> = {
  verify: "bg-verify",
  risk: "bg-risk",
  caution: "bg-caution",
  neutral: "bg-neutral",
}

export function StatusMarker({ tone, className = "" }: { tone: MarkerTone; className?: string }) {
  return <span className={`inline-block h-2.5 w-2.5 shrink-0 ${shapeByTone[tone]} ${colorByTone[tone]} ${className}`} />
}

export function StatusBadge({ tone, label }: { tone: MarkerTone; label: string }) {
  const bgByTone: Record<MarkerTone, string> = {
    verify: "bg-verify-bg text-verify",
    risk: "bg-risk-bg text-risk",
    caution: "bg-caution-bg text-caution",
    neutral: "bg-neutral-bg text-neutral",
  }
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-[4px] px-2 py-1 text-xs font-medium ${bgByTone[tone]}`}>
      <StatusMarker tone={tone} />
      {label}
    </span>
  )
}

export type { MarkerTone }

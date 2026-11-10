import { BackendStatus } from "./BackendStatus"

export function Header() {
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-[1180px] flex-wrap items-center justify-between gap-3 px-6 py-5">
        <div>
          <h1 className="font-display text-xl font-semibold leading-tight">AI Hallucination Detector</h1>
          <p className="text-sm text-ink-muted">Evidence-based verification for AI-generated answers</p>
        </div>
        <BackendStatus />
      </div>
    </header>
  )
}

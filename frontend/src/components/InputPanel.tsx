import { useState } from "react"
import type { AnalysisMode } from "../types/detector"
import { examplePrompts } from "../utils/examples"

const MAX_CHARS = 4000

const modes: { value: AnalysisMode; label: string; hint: string }[] = [
  { value: "quick", label: "Quick", hint: "KB-only, no logic/cross-model check" },
  { value: "standard", label: "Standard", hint: "Full verification, web evidence" },
  { value: "deep", label: "Deep", hint: "Same as Standard, lower concurrency" },
]

interface Props {
  value: string
  onChange: (value: string) => void
  mode: AnalysisMode
  onModeChange: (mode: AnalysisMode) => void
  onAnalyze: () => void
  disabled: boolean
}

export function InputPanel({ value, onChange, mode, onModeChange, onAnalyze, disabled }: Props) {
  const [validationMessage, setValidationMessage] = useState<string | null>(null)

  const overLimit = value.length > MAX_CHARS
  const trimmedEmpty = value.trim().length === 0

  function handleAnalyzeClick() {
    if (trimmedEmpty) {
      setValidationMessage("Please enter a question or prompt to analyze.")
      return
    }
    if (overLimit) {
      setValidationMessage(`Please shorten this to ${MAX_CHARS} characters or fewer.`)
      return
    }
    setValidationMessage(null)
    onAnalyze()
  }

  return (
    <section className="rounded-[6px] border border-border bg-surface p-6">
      <h2 className="font-display text-lg font-semibold">Ask a question to verify</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Enter a question or prompt. The AI will generate an answer, then each factual claim in that answer will be
        checked against evidence.
      </p>

      <textarea
        className="mt-4 h-40 w-full resize-y rounded-[4px] border border-border bg-bg p-3 text-sm text-ink placeholder:text-ink-faint focus-visible:outline-2 focus-visible:outline-ink"
        placeholder="Ask a question… (e.g. “When was the Eiffel Tower built?”)"
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          if (validationMessage) setValidationMessage(null)
        }}
        disabled={disabled}
      />

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-faint">
        <span className={overLimit ? "text-risk" : ""}>
          {value.length.toLocaleString()} / {MAX_CHARS.toLocaleString()} characters
        </span>
        <div className="flex gap-3">
          {examplePrompts.map((ex) => (
            <button
              key={ex.label}
              type="button"
              className="underline decoration-border-strong underline-offset-2 hover:text-ink-muted"
              onClick={() => onChange(ex.text)}
              disabled={disabled}
            >
              Try: "{ex.label}"
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-4">
        <fieldset className="flex gap-2">
          <legend className="sr-only">Analysis mode</legend>
          {modes.map((m) => (
            <button
              key={m.value}
              type="button"
              title={m.hint}
              aria-pressed={mode === m.value}
              className={`rounded-[4px] border px-3 py-1.5 text-sm transition-colors ${
                mode === m.value
                  ? "border-ink bg-ink text-surface"
                  : "border-border bg-surface text-ink-muted hover:border-border-strong"
              }`}
              onClick={() => onModeChange(m.value)}
              disabled={disabled}
            >
              {m.label}
            </button>
          ))}
        </fieldset>

        <div className="flex items-center gap-3">
          <button
            type="button"
            className="text-sm text-ink-muted underline decoration-border-strong underline-offset-2 hover:text-ink"
            onClick={() => onChange("")}
            disabled={disabled || value.length === 0}
          >
            Clear
          </button>
          <button
            type="button"
            className="rounded-[4px] bg-ink px-4 py-2 text-sm font-medium text-surface hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={handleAnalyzeClick}
            disabled={disabled}
          >
            Ask &amp; verify
          </button>
        </div>
      </div>

      {validationMessage && (
        <p className="mt-3 text-sm text-risk" role="alert">
          {validationMessage}
        </p>
      )}
    </section>
  )
}

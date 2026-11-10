import { useState } from "react"
import { InputPanel } from "../components/InputPanel"
import { AnalyzingState } from "../components/AnalyzingState"
import { ErrorState } from "../components/ErrorState"
import { SummaryCard } from "../components/SummaryCard"
import { ClaimsList } from "../components/ClaimsList"
import { CitationsList } from "../components/CitationsList"
import { VerificationBreakdown } from "../components/VerificationBreakdown"
import { PerformancePanel } from "../components/PerformancePanel"
import { analyzeAnswer } from "../api/detector"
import type { AnalysisMode, AnalysisResponse } from "../types/detector"
import ReactMarkdown from "react-markdown"

export function Dashboard() {
  const [promptText, setPromptText] = useState("")
  const [mode, setMode] = useState<AnalysisMode>("standard")
  const [status, setStatus] = useState<"idle" | "loading" | "error" | "done">("idle")
  const [result, setResult] = useState<AnalysisResponse | null>(null)
  const [error, setError] = useState<unknown>(null)

  async function runAnalysis() {
    setStatus("loading")
    setError(null)
    try {
      const response = await analyzeAnswer(promptText, mode)
      setResult(response)
      setStatus("done")
    } catch (err) {
      setError(err)
      setStatus("error")
    }
  }

  return (
    <div className="mx-auto max-w-[1180px] px-6 py-8">
      <InputPanel
        value={promptText}
        onChange={setPromptText}
        mode={mode}
        onModeChange={setMode}
        onAnalyze={runAnalysis}
        disabled={status === "loading"}
      />

      {status === "loading" && <AnalyzingState />}
      {status === "error" && <ErrorState error={error} onRetry={runAnalysis} />}

      {status === "done" && result && (
        <div className="mt-6 space-y-6">
          <div>
            <p className="text-xs font-medium text-ink-faint">AI-generated answer (this is what was verified)</p>
            <p className="mt-1 whitespace-pre-wrap rounded-[6px] border border-border bg-surface p-4 text-sm text-ink-muted">
              <div className="answer-content">
                <ReactMarkdown
                  components={{
                    strong: ({ children }) => <strong>{children}</strong>,
                    ul: ({ children }) => <ul>{children}</ul>,
                    li: ({ children }) => <li>{children}</li>,
                  }}
                >
                  {result.answer}
                </ReactMarkdown>
              </div>

            </p>
          </div>

          <SummaryCard result={result} />

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px] lg:items-start">
            <div className="space-y-6">
              <ClaimsList claims={result.claims} />
              <CitationsList citations={result.citations} />
            </div>
            <div className="space-y-6">
              <VerificationBreakdown scores={result.module_scores} />
              <PerformancePanel latency={result.latency} mode={result.mode} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

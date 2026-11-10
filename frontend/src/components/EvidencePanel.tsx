import type { ClaimReport } from "../types/detector"

export function EvidencePanel({ claim }: { claim: ClaimReport }) {
  if (!claim.evidence) {
    return (
      <p className="text-sm italic text-ink-faint">
        No evidence was found for this claim in the knowledge base or web search.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs font-medium text-ink-faint">Evidence</p>
        <p className="mt-1 whitespace-pre-wrap text-sm text-ink-muted">{claim.evidence}</p>
      </div>

      {claim.sources.length > 0 && (
        <div>
          <p className="text-xs font-medium text-ink-faint">Sources</p>
          <ul className="mt-1 space-y-1">
            {claim.sources.map((source, i) => (
              <li key={i} className="text-sm">
                {source.url ? (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-ink underline decoration-border-strong underline-offset-2 hover:text-ink-muted"
                  >
                    {source.title || source.url}
                  </a>
                ) : (
                  <span className="text-ink-muted">{source.title || "Untitled source"}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {claim.error && (
        <p className="text-xs text-risk">Verification for this claim hit an error: {claim.error}</p>
      )}
    </div>
  )
}

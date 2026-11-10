import type { CitationReport } from "../types/detector"
import { StatusBadge } from "./StatusMarker"
import { citationVerdictDisplay } from "../utils/display"

const typeLabel: Record<CitationReport["type"], string> = {
  url: "Link",
  numbered: "Numbered reference",
  author_year: "Author/year reference",
}

export function CitationsList({ citations }: { citations: CitationReport[] }) {
  if (citations.length === 0) {
    return (
      <section className="rounded-[6px] border border-border bg-surface p-6">
        <h2 className="font-display text-lg font-semibold">Citations</h2>
        <p className="mt-2 text-sm text-ink-faint">
          No citations were found in the text. That's neutral, not a problem -- most correct answers cite nothing.
        </p>
      </section>
    )
  }

  return (
    <section className="rounded-[6px] border border-border bg-surface p-6">
      <h2 className="font-display text-lg font-semibold">Citations</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Links are checked for reachability. Reachable only means the source exists and responds -- not that it
        proves the claim. References without a URL can't be resolved from text alone.
      </p>
      <ul className="mt-4 space-y-3">
        {citations.map((c, i) => {
          const display = citationVerdictDisplay[c.verdict]
          return (
            <li key={i} className="flex items-start justify-between gap-4 border-t border-border pt-3 first:border-t-0 first:pt-0">
              <div>
                <p className="text-xs text-ink-faint">{typeLabel[c.type]}</p>
                {c.type === "url" ? (
                  <a
                    href={c.text}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-0.5 block break-all text-sm text-ink underline decoration-border-strong underline-offset-2 hover:text-ink-muted"
                  >
                    {c.text}
                  </a>
                ) : (
                  <p className="mt-0.5 text-sm text-ink">{c.text}</p>
                )}
              </div>
              <StatusBadge tone={display.tone} label={display.label} />
            </li>
          )
        })}
      </ul>
    </section>
  )
}

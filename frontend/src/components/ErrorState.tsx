import { ApiError } from "../types/detector"

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.kind) {
      case "network":
        return "Unable to connect to the verification service. Please try again. (If this keeps happening: the backend may be down, or may not be configured to allow requests from this site -- check the browser console for details.)"
      case "timeout":
      case "server_timeout":
        return "The analysis is taking longer than expected. Please try again."
      case "validation":
        return error.message || "Please check your input and try again."
      case "rate_limited":
        return error.retryAfterSeconds
          ? `Too many requests -- please wait about ${error.retryAfterSeconds}s and try again.`
          : "Too many requests -- please wait a moment and try again."
      case "payload_too_large":
        return "That question is too long. Please shorten it."
      case "not_found":
        return "The verification service endpoint could not be found. Please try again later."
      case "server_error":
        return "Something went wrong while generating and verifying the answer."
      default:
        return "Something went wrong while generating and verifying the answer."
    }
  }
  return "Something went wrong while generating and verifying the answer."
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="mt-6 rounded-[6px] border border-risk/30 bg-risk-bg p-5" role="alert">
      <p className="text-sm font-medium text-risk">{messageFor(error)}</p>
      {onRetry && (
        <button
          type="button"
          className="mt-3 rounded-[4px] border border-risk/40 px-3 py-1.5 text-sm text-risk hover:bg-risk/10"
          onClick={onRetry}
        >
          Try again
        </button>
      )}
    </div>
  )
}

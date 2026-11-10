import { ApiError } from "../types/detector"

// Vite exposes env vars prefixed VITE_ on import.meta.env at build time.
// Falls back to localhost:8000 (the backend's default uvicorn port) for
// local dev if the env var isn't set. In production this MUST be set via
// VITE_API_URL at build time (see .env.example) -- otherwise a deployed
// frontend will silently try to call localhost, which doesn't exist in
// the browser running it.
const BASE_URL =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ??
  "https://ai-hallucination-detector-1.onrender.com"

console.log("API BASE URL:", BASE_URL)
// TIMEOUT ALIGNMENT: the backend (app/config.py: REQUEST_TIMEOUT_SECONDS)
// enforces a hard 60s ceiling on total request processing and returns a
// clean 504 JSON body if it's hit. This client timeout is intentionally
// set well above that so the backend's own 504 response has time to
// actually arrive -- if this were set at or below 60s, the client would
// abort first and we'd see a generic client-side "timeout" instead of the
// backend's real 504, which is strictly less informative. Keep this above
// (backend REQUEST_TIMEOUT_SECONDS * 1000) with margin if either changes.
const CLIENT_TIMEOUT_MS = 90_000

interface RequestOptions {
  method?: "GET" | "POST"
  body?: unknown
  timeoutMs?: number
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, timeoutMs = CLIENT_TIMEOUT_MS } = options

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
  } catch (err) {
    clearTimeout(timer)
    if (err instanceof DOMException && err.name === "AbortError") {
      const timeoutError = new ApiError("timeout", "The request took too long and was cancelled.")
      logDebug(timeoutError, { path, method, timeoutMs, base: BASE_URL })
      throw timeoutError
    }
    // The Fetch API deliberately gives JS no way to distinguish "backend is
    // down / unreachable" from "backend responded but the browser blocked
    // it due to CORS" -- both surface as the same opaque network failure
    // (e.g. TypeError: Failed to fetch), by browser design, for security
    // reasons. We can't fix that from here; the debug log below at least
    // prints the exact URL/origin involved so a developer can check the
    // Network tab for a CORS-specific console warning the browser itself
    // prints (which JS still can't read, but a human can see it).
    const networkError = new ApiError(
      "network",
      "Could not reach the verification service."
    )
    logDebug(networkError, { path, method, base: BASE_URL, rawError: err, hint: "Could be backend down, network issue, or a CORS rejection -- check the browser console/Network tab for a CORS warning." })
    throw networkError
  }
  clearTimeout(timer)

  if (!response.ok) {
    const apiError = await toApiError(response)
    logDebug(apiError, { path, method, status: response.status, base: BASE_URL })
    throw apiError
  }

  try {
    return (await response.json()) as T
  } catch (err) {
    const parseError = new ApiError("unknown", "The server returned a response that couldn't be read.")
    logDebug(parseError, { path, method, base: BASE_URL, rawError: err })
    throw parseError
  }
}

// Prints full technical detail to the console for developers, while the
// ApiError.message shown in the UI stays short and user-friendly. Errors
// are always distinguishable during debugging via error.kind + this log,
// even when the user-facing copy is intentionally generic.
function logDebug(error: ApiError, context: Record<string, unknown>) {
  // eslint-disable-next-line no-console
  console.error(`[api] ${error.kind}${error.status ? ` (${error.status})` : ""}: ${error.message}`, context)
}

async function toApiError(response: Response): Promise<ApiError> {
  let bodyMessage: string | undefined
  try {
    const data = await response.json()
    // FastAPI validation errors: {"detail": [{"msg": ...}, ...]}
    // Our custom error handlers: {"error": "..."}
    if (typeof data?.error === "string") {
      bodyMessage = data.error
    } else if (Array.isArray(data?.detail) && data.detail.length > 0) {
      bodyMessage = data.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ")
    } else if (typeof data?.detail === "string") {
      bodyMessage = data.detail
    }
  } catch {
    // body wasn't JSON -- fall through with no extra detail
  }

  switch (response.status) {
    case 404:
      return new ApiError(
        "not_found",
        bodyMessage ?? "That endpoint doesn't exist on the backend.",
        404
      )
    case 422:
      return new ApiError("validation", bodyMessage ?? "Please check your input.", 422)
    case 413:
      return new ApiError("payload_too_large", bodyMessage ?? "That input is too large.", 413)
    case 429: {
      const retryAfter = Number(response.headers.get("Retry-After"))
      return new ApiError(
        "rate_limited",
        bodyMessage ?? "Too many requests -- please slow down.",
        429,
        Number.isFinite(retryAfter) ? retryAfter : undefined
      )
    }
    case 504:
      return new ApiError("server_timeout", bodyMessage ?? "The analysis timed out.", 504)
    case 500:
      return new ApiError("server_error", bodyMessage ?? "Something went wrong on the server.", 500)
    default:
      return new ApiError("unknown", bodyMessage ?? `Unexpected error (${response.status}).`, response.status)
  }
}

export { BASE_URL }

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { apiRequest } from "../api/client"
import { ApiError } from "../types/detector"

function mockFetchResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (key: string) => headers[key] ?? null },
    json: async () => body,
  } as Response
}

describe("apiRequest error normalization", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("returns parsed JSON on success", async () => {
    vi.mocked(fetch).mockResolvedValue(mockFetchResponse(200, { answer: "hi" }))
    const result = await apiRequest<{ answer: string }>("/ask")
    expect(result.answer).toBe("hi")
  })

  it("maps 422 to a validation ApiError with pydantic detail joined", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockFetchResponse(422, { detail: [{ msg: "prompt must not be blank" }] })
    )
    await expect(apiRequest("/ask")).rejects.toMatchObject({
      kind: "validation",
      message: "prompt must not be blank",
    })
  })

  it("maps 413 to payload_too_large", async () => {
    vi.mocked(fetch).mockResolvedValue(mockFetchResponse(413, { error: "request body too large" }))
    await expect(apiRequest("/ask")).rejects.toMatchObject({ kind: "payload_too_large" })
  })

  it("maps 429 to rate_limited and reads Retry-After header", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockFetchResponse(429, { error: "rate limit exceeded, please slow down" }, { "Retry-After": "12" })
    )
    await expect(apiRequest("/ask")).rejects.toMatchObject({
      kind: "rate_limited",
      retryAfterSeconds: 12,
    })
  })

  it("maps 404 to not_found", async () => {
    vi.mocked(fetch).mockResolvedValue(mockFetchResponse(404, { detail: "Not Found" }))
    await expect(apiRequest("/nonexistent")).rejects.toMatchObject({ kind: "not_found", status: 404 })
  })

  it("maps 500 to server_error without leaking backend detail structure", async () => {
    vi.mocked(fetch).mockResolvedValue(mockFetchResponse(500, { error: "internal server error" }))
    await expect(apiRequest("/ask")).rejects.toMatchObject({ kind: "server_error" })
  })

  it("maps 504 to server_timeout", async () => {
    vi.mocked(fetch).mockResolvedValue(mockFetchResponse(504, { error: "request timed out" }))
    await expect(apiRequest("/ask")).rejects.toMatchObject({ kind: "server_timeout" })
  })

  it("maps a network failure (fetch throws) to a network ApiError", async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError("Failed to fetch"))
    await expect(apiRequest("/ask")).rejects.toBeInstanceOf(ApiError)
    await expect(apiRequest("/ask")).rejects.toMatchObject({ kind: "network" })
  })

  it("maps an aborted request (client timeout) to a timeout ApiError", async () => {
    vi.mocked(fetch).mockRejectedValue(new DOMException("aborted", "AbortError"))
    await expect(apiRequest("/ask")).rejects.toMatchObject({ kind: "timeout" })
  })
})

import { apiRequest } from "./client"
import type { AnalysisMode, AnalysisResponse, HealthResponse } from "../types/detector"

export function analyzeAnswer(prompt: string, mode: AnalysisMode): Promise<AnalysisResponse> {
  return apiRequest<AnalysisResponse>("/ask", {
    method: "POST",
    body: { prompt, mode },
  })
}

export function getHealth(timeoutMs = 8_000): Promise<HealthResponse> {
  // Health checks default to failing fast -- no need for the full 90s
  // client timeout. BackendStatus overrides this with a longer timeout
  // while handling Render cold starts (see BackendStatus.tsx).
  return apiRequest<HealthResponse>("/health", { timeoutMs })
}

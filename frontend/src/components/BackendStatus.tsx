import { useEffect, useRef, useState } from "react"
import { getHealth } from "../api/detector"
import { StatusMarker } from "./StatusMarker"

type Status = "checking" | "waking" | "online" | "offline"

const STEADY_STATE_POLL_MS = 30_000

// Render's free tier spins the backend down after inactivity; the first
// request after that can take 30-60+ seconds to wake it up. A single
// short-timeout health check would misreport that as "API unavailable"
// when it's actually just waking up. Instead: retry with backoff for a
// while before concluding it's genuinely offline.
const WAKE_RETRY_DELAYS_MS = [3_000, 5_000, 8_000, 8_000, 8_000, 8_000, 8_000, 8_000, 8_000, 8_000] // ~74s total
const HEALTH_CHECK_TIMEOUT_MS = 10_000

export function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking")
  const attemptRef = useRef(0)
  const cancelledRef = useRef(false)

  useEffect(() => {
    cancelledRef.current = false

    async function attempt() {
      try {
        await getHealth(HEALTH_CHECK_TIMEOUT_MS)
        if (cancelledRef.current) return
        setStatus("online")
        attemptRef.current = 0
        scheduleNext(STEADY_STATE_POLL_MS)
        return
      } catch {
        if (cancelledRef.current) return
      }

      const nextDelay = WAKE_RETRY_DELAYS_MS[attemptRef.current]
      if (nextDelay === undefined) {
        // exhausted the wake-up retry budget -- genuinely treat as offline,
        // but keep polling at the steady-state interval in case it recovers
        setStatus("offline")
        scheduleNext(STEADY_STATE_POLL_MS)
        return
      }

      setStatus((prev) => (prev === "online" ? "offline" : "waking"))
      attemptRef.current += 1
      scheduleNext(nextDelay)
    }

    let timer: ReturnType<typeof setTimeout>
    function scheduleNext(delay: number) {
      timer = setTimeout(attempt, delay)
    }

    attempt()
    return () => {
      cancelledRef.current = true
      clearTimeout(timer)
    }
  }, [])

  const label =
    status === "checking"
      ? "Checking API…"
      : status === "waking"
        ? "Waking up API… this can take a few seconds"
        : status === "online"
          ? "API connected"
          : "API unavailable"
  const tone = status === "online" ? "verify" : status === "offline" ? "risk" : "neutral"

  return (
    <div className="flex items-center gap-2 text-sm text-ink-muted">
      <StatusMarker tone={tone} className={status === "waking" || status === "checking" ? "animate-pulse" : ""} />
      <span>{label}</span>
    </div>
  )
}

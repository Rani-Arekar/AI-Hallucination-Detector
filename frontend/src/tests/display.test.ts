import { describe, it, expect } from "vitest"
import { riskBand, formatMs, formatPercent, claimVerdictDisplay, citationVerdictDisplay } from "../utils/display"

describe("riskBand", () => {
  it("bands below 30 as low risk", () => {
    expect(riskBand(0).label).toBe("Low risk")
    expect(riskBand(29).label).toBe("Low risk")
  })
  it("bands 30-59 as medium risk", () => {
    expect(riskBand(30).label).toBe("Medium risk")
    expect(riskBand(59).label).toBe("Medium risk")
  })
  it("bands 60+ as high risk", () => {
    expect(riskBand(60).label).toBe("High risk")
    expect(riskBand(100).label).toBe("High risk")
  })
})

describe("formatMs", () => {
  it("returns null for undefined (stage not run)", () => {
    expect(formatMs(undefined)).toBeNull()
  })
  it("formats sub-second values in ms", () => {
    expect(formatMs(450)).toBe("450 ms")
  })
  it("formats values >= 1000ms in seconds", () => {
    expect(formatMs(1500)).toBe("1.50 s")
  })
})

describe("formatPercent", () => {
  it("rounds to nearest whole percent", () => {
    expect(formatPercent(0.876)).toBe("88%")
    expect(formatPercent(1.0)).toBe("100%")
    expect(formatPercent(0)).toBe("0%")
  })
})

describe("verdict display maps cover every backend enum value", () => {
  it("has an entry for every claim verdict the backend can return", () => {
    const verdicts = ["SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED", "UNCERTAIN", "INSUFFICIENT_EVIDENCE"]
    for (const v of verdicts) {
      expect(claimVerdictDisplay[v as keyof typeof claimVerdictDisplay]).toBeDefined()
    }
  })

  it("has an entry for every citation verdict the backend can return", () => {
    const verdicts = ["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "NO_SOURCE"]
    for (const v of verdicts) {
      expect(citationVerdictDisplay[v as keyof typeof citationVerdictDisplay]).toBeDefined()
    }
  })
})

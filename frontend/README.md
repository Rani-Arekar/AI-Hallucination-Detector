# AI Hallucination Detector — Frontend

A standalone React + TypeScript + Tailwind dashboard for the existing
FastAPI backend. Ask a question; the backend generates an answer with
Gemini and this UI shows the claim-level verification of that answer
against evidence, with an explainable breakdown of how the risk score was
computed.

This frontend is read-only against the backend API — it does not modify
backend logic, and every value it displays comes directly from what the
API actually returns. See `src/types/detector.ts` for the exact response
shape this UI assumes.

## Requirements

- Node.js 20+
- The backend running and reachable (locally or deployed)

## Setup

```bash
npm install
cp .env.example .env
# edit .env: set VITE_API_URL to your backend's URL
npm run dev
```

Opens on `http://localhost:5173` by default.

## Scripts

```bash
npm run dev       # local dev server
npm run build     # type-check + production build to dist/
npm run preview   # serve the production build locally
npm run lint       # oxlint
npm run test       # vitest (API client + display-logic unit tests)
```

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_URL` | Base URL of the FastAPI backend, no trailing slash | `http://localhost:8000` |

Set via `.env` locally, or as a build-time environment variable on your
deployment platform (Vercel/Netlify). Vite inlines `VITE_*` vars at build
time, so this must be set *before* `npm run build` runs on the deploy
platform, not just at runtime.

**The real deployed backend for this project is on Render:**
```
VITE_API_URL=https://ai-hallucination-detector-1.onrender.com
```
Set this as a build-time env var on your frontend hosting platform for
production builds — the `http://localhost:8000` default is for local dev
only and will not work once the frontend is deployed somewhere a browser
loads it from (there is no `localhost:8000` on the visitor's machine).

## Backend CORS configuration

The backend's CORS policy (`ALLOWED_ORIGINS` in `app/config.py`) defaults
to `http://localhost:5173` (Vite's default dev port) — this already
matches `npm run dev` out of the box for local development. For a deployed
frontend, set on the backend's Render deployment:

```
ALLOWED_ORIGINS=http://localhost:5173,https://your-frontend-domain.vercel.app
```

This is a deployment configuration change (an env var), not a backend code
change.

## Render cold starts

If the backend is on Render's free tier, it spins down after a period of
inactivity and the first request afterward can take 30-60+ seconds to wake
it back up. This frontend handles that explicitly rather than immediately
reporting "API unavailable":

- The header status indicator retries the health check with backoff for
  roughly a minute (showing "Waking up API…") before concluding the
  backend is genuinely offline.
- The client-side request timeout for `/ask` (90s) is intentionally set
  well above the backend's own hard processing timeout (60s, see
  `REQUEST_TIMEOUT_SECONDS` in the backend's `app/config.py`) so that a
  slow-but-working request — including one hitting a cold start — has
  room to complete, and so the backend's own clean `504` response (if it
  is genuinely hit) has time to arrive rather than being pre-empted by the
  client aborting first. If you change the backend's timeout, keep this
  client timeout comfortably above it.

## Deployment (Vercel or Netlify)

1. Push this repo (or just the `frontend/` directory as its own project)
2. Import into Vercel/Netlify
3. Build command: `npm run build`, output directory: `dist`
4. Set `VITE_API_URL` as a build-time environment variable in the
   platform's project settings (see above for the real backend URL)
5. Set the backend's `ALLOWED_ORIGINS` to include the deployed frontend URL
   (see above) — do this before/at the same time as deploying, or the
   deployed frontend will get CORS errors calling the API

## Error handling / debugging

Every failed request is normalized into an `ApiError` with a `kind`
(`network`, `timeout`, `validation`, `rate_limited`, `payload_too_large`,
`not_found`, `server_timeout`, `server_error`, `unknown`) and logged to the
browser console with full technical detail (status code, URL, raw error)
via `console.error`, even though the on-screen message stays short and
user-friendly. Check the console when debugging a failed request.

One real browser limitation, not a bug here: the Fetch API deliberately
gives JavaScript no way to distinguish "backend is down/unreachable" from
"backend responded but the browser blocked it via CORS" — both surface as
the same opaque failure, by browser design, for security reasons. Both are
reported as `kind: "network"`; if you hit this, check the browser's
Network tab / console for a CORS-specific warning that only the browser
(not this app's JS) can see.

## What this UI does and doesn't do

- The flow is **ask a question → backend generates an answer → that answer
  gets verified** — not "paste an existing answer to check." The input box
  asks for a question/prompt accordingly.
- Shows only fields the backend actually returns — nothing is invented.
  `logic_ms` / `cross_model_ms` are absent (not zero) in Quick mode since
  those checks are skipped, and the UI reflects that explicitly rather
  than showing a fake `0ms`.
- The loading state is an indeterminate spinner with a generic message,
  not a fake per-stage checklist — the backend is a single synchronous
  request and doesn't stream progress, so a "✓ Extracting claims" style
  live stepper would be fabricated.
- Risk-score bands (Low/Medium/High) and the "heuristic, not calibrated"
  language mirror how the backend's own scoring module (`app/detector/scoring.py`)
  describes itself.

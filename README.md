# AI Hallucination Detector

## Integration API

The FastAPI backend is also used by the parent HalluciDetect frontend. The
frontend calls `POST /api/analyze` with already-generated text; this endpoint
does not generate a replacement answer. Configure the frontend with
`VITE_API_BASE_URL` and configure the backend with `GEMINI_API_KEY` and
`ALLOWED_ORIGINS`.

The existing `POST /ask` endpoint remains available for the original
prompt-to-generated-answer workflow.

`verification_mode` from the parent UI maps `standard` to the reference
pipeline's `standard` mode and `strict` to `deep`. Evidence source selection
controls local knowledge-base and web retrieval, and sentence granularity uses
deterministic sentence splitting. `confidence_threshold` is validated and
returned for compatibility, but the reference pipeline only exposes a
response-level confidence signal and does not apply a per-claim threshold.

The backend in this repository is adapted under the MIT license. The original
copyright and license notice in `LICENSE` must remain with redistributed
copies or substantial portions of the reused source.

## Claim scoring methodology

The analysis API exposes `scoring_methodology_version:
"claim-heuristic-v1"`. These values are transparent heuristic signals, not
calibrated probabilities.

For a claim with useful evidence:

```text
hallucination risk = round(100 * (1 - evidence support signal))
```

The support signal is `1.0` for `SUPPORTED`, `0.65` for
`PARTIALLY_SUPPORTED`, `0.0` for `CONTRADICTED`, and `0.5` for uncertain or
unverifiable classifications. A contradicted claim with useful evidence is
assigned 100 risk. A claim with no useful evidence is assigned a neutral 50
risk and low decision confidence; missing evidence is not treated as proof of
hallucination.

Decision confidence combines independent verification signals:

```text
confidence =
  0.35 * source credibility
  + 0.25 * semantic relevance (or a neutral fallback when unavailable)
  + 0.25 * source agreement
  + 0.15 * logical consistency
```

Semantic similarity is only one confidence input and never determines
correctness by itself. Source credibility is a conservative heuristic:
`.gov`/`.edu` hosts receive more weight than `.org`, other web hosts, or
unknown sources; configured local knowledge-base evidence is treated as a
high-quality source. Agreement increases when multiple distinct URLs or
source types are present.

Overall risk is a confidence-weighted average of claim risk. Each claim has a
minimum weight of `0.25`, so low-evidence claims remain visible in the
overall result. Overall reliability is `100 - overall hallucination risk`.
The methodology has not been evaluated against a labeled dataset and must not
be described as a calibrated probability.

Future calibration can be added as a separate module using a held-out
labeled dataset. It should learn a mapping from these signals and raw
verdicts to calibrated probabilities without changing the transparent base
scores. An optional empirical-bin implementation is available in
`app/detector/calibration.py`; it is intentionally not invoked by the live
API until a representative held-out dataset and calibration evaluation exist.

Evidence-based verification of AI-generated answers using claim extraction, semantic retrieval, web evidence, and LLM-based verification.

The system generates an answer from a user prompt, extracts factual claims from that answer, evaluates those claims against available evidence, and presents an explainable verification result through a React frontend.

## Live Application

**Frontend:** https://frontend-coral-one-6cme2r1fvt.vercel.app/

**Backend API:** https://ai-hallucination-detector-1.onrender.com

**API Health Check:** https://ai-hallucination-detector-1.onrender.com/health

---

## Overview

Large language models can generate fluent and convincing answers that contain unsupported or incorrect factual claims.

This project explores a practical approach to detecting such claims by combining:

- LLM-generated answers
- Claim extraction
- Semantic similarity search
- Local knowledge retrieval
- Web evidence retrieval
- LLM-based evidence verification
- Claim-level scoring
- Explainable verification results
- Performance and backend status monitoring

Instead of treating hallucination detection as a single black-box classification problem, the application breaks an answer into individual claims and evaluates those claims against evidence.

### Example

A user asks:

> "When was the Eiffel Tower built, and how tall is it?"

The system:

```text
User Prompt
     ↓
Answer Generation
     ↓
Claim Extraction
     ↓
 ┌───────────────┐
 │ Claim 1       │ → Evidence retrieval → Verification
 │ Claim 2       │ → Evidence retrieval → Verification
 │ Claim 3       │ → Evidence retrieval → Verification
 └───────────────┘
     ↓
Evidence Aggregation
     ↓
Reliability Analysis
     ↓
Explainable UI
```

---

# Key Features

## 1. Claim-Level Verification

Rather than assigning a single score to an entire answer, the system breaks the generated response into factual claims.

Each claim can then be evaluated independently.

This makes the result easier to inspect and explain.

---

## 2. Evidence-Based Verification

Claims can be evaluated using multiple evidence sources:

* Local semantic knowledge base
* Web search results
* LLM-based verification
* Logical / linguistic signals

The goal is to provide evidence-backed verification instead of relying entirely on model confidence.

---

## 3. Semantic Retrieval

The application uses Google's embedding API to generate semantic representations of text.

Current embedding implementation uses:

```text
gemini-embedding-001
```

The local vector store compares query and document embeddings using cosine similarity.

This keeps the deployment lightweight compared with running a local transformer embedding model.

---

## 4. Web Evidence Retrieval

The application can retrieve supporting information from web search results for factual claims.

This provides a second evidence source beyond the local knowledge base.

Web retrieval is particularly useful when a claim is not covered by the local documents.

---

## 5. LLM-Based Verification

Retrieved evidence is passed to a verifier model which evaluates whether the evidence supports the claim.

The verifier is instructed to return:

```text
YES
NO
UNCERTAIN
```

These results are converted into verification signals used by the scoring pipeline.

---

## 6. Multiple Analysis Modes

The frontend provides three analysis modes:

| Mode     | Purpose                                 |
| -------- | --------------------------------------- |
| Quick    | Faster analysis with reduced processing |
| Standard | Balanced verification                   |
| Deep     | More detailed verification              |

The exact latency and verification depth depend on the backend processing and external API response times.

---

# Architecture

```text
                         ┌──────────────────────┐
                         │      React / Vite    │
                         │      Frontend        │
                         │                      │
                         │ Input                │
                         │ Results              │
                         │ Claims               │
                         │ Evidence             │
                         │ Performance          │
                         └──────────┬───────────┘
                                    │
                                    │ HTTPS
                                    ▼
                         ┌──────────────────────┐
                         │      FastAPI         │
                         │      Backend         │
                         └──────────┬───────────┘
                                    │
                     ┌──────────────┼──────────────┐
                     │              │              │
                     ▼              ▼              ▼
              ┌────────────┐ ┌────────────┐ ┌─────────────┐
              │   Gemini   │ │  Semantic  │ │  Web Search │
              │    LLM     │ │ Retrieval  │ │    (DDGS)   │
              └────────────┘ └────────────┘ └─────────────┘
                     │              │              │
                     └──────────────┼──────────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ Evidence Verification│
                         │ & Scoring Pipeline   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Structured API Result │
                         └──────────────────────┘
```

---

# Technology Stack

## Frontend

* React
* TypeScript
* Vite
* React Markdown
* CSS

The frontend was migrated from the original Streamlit prototype to a standalone React application to provide a more flexible production-style user interface.

## Backend

* Python
* FastAPI
* Pydantic
* Uvicorn

## AI / ML

* Google Gemini
* `gemini-embedding-001`
* Semantic similarity
* LLM-based verification

## Retrieval

* Local in-memory vector store
* Cosine similarity
* DuckDuckGo Search (`ddgs`)

## Deployment

* Vercel — frontend
* Render — backend

---

# Backend Engineering Improvements

The initial implementation was functional but had several issues that became apparent during production-oriented testing.

The backend was subsequently cleaned up and modified with deployment reliability, resource usage, and API robustness in mind.

## 1. Removed Heavy Local Embedding Dependencies

The original implementation used:

```text
sentence-transformers
FAISS
PyTorch
```

This created unnecessary memory pressure for a small Render deployment.

The application was migrated to Google's hosted embedding API:

```text
gemini-embedding-001
```

This significantly reduces the amount of ML infrastructure that needs to run inside the API container.

### Result

The backend no longer needs to load a large local transformer model into memory.

This was particularly important because the application is deployed on a resource-constrained hosting environment.

---

## 2. Migrated to the Current Google GenAI SDK

The backend uses:

```python
from google import genai
```

instead of the older:

```python
google-generativeai
```

This keeps the implementation aligned with the current Google GenAI Python SDK.

---

## 3. Environment-Based Secret Management

API credentials are not stored directly in source code.

The application reads:

```text
GEMINI_API_KEY
```

from environment variables.

Local development can use a `.env` file while production credentials are configured through the hosting platform.

### Security principle

Secrets should never be committed to Git.

The repository should therefore contain only configuration examples such as:

```text
.env.example
```

and never the actual API key.

---

## 4. CORS Configuration

The API explicitly controls which frontend origins are allowed to access the backend.

For example:

```text
http://localhost:5173
http://localhost:5174
https://your-production-frontend.vercel.app
```

Production origins are configured through:

```text
ALLOWED_ORIGINS
```

This prevents the API from relying on an unrestricted wildcard CORS policy.

---

## 5. API Error Handling

The frontend distinguishes between several backend/network failure conditions, including:

* Network failure
* Request timeout
* Validation error
* Not found
* Payload too large
* Rate limiting
* Server error
* Gateway timeout

This allows the UI to provide meaningful feedback instead of simply displaying:

```text
Failed to fetch
```

---

## 6. Request Timeout Handling

The frontend uses an `AbortController` to prevent indefinitely hanging requests.

The current client-side timeout is:

```text
90 seconds
```

If the backend takes longer than the configured limit, the request is cancelled and the UI displays an appropriate timeout message.

This is particularly important because the verification pipeline depends on external AI and web services.

---

## 7. Structured API Communication

The frontend communicates with the FastAPI backend through a centralized API client rather than scattering raw `fetch()` calls throughout UI components.

This provides a single place for:

* Base URL configuration
* Timeout handling
* HTTP error handling
* JSON parsing
* Debug logging
* API error classification

---

## 8. Lightweight Deployment Architecture

The production architecture intentionally avoids unnecessary infrastructure.

```text
Vercel
  │
  │ HTTPS
  ▼
FastAPI on Render
  │
  ├── Gemini
  ├── Gemini Embeddings
  └── Web Search
```

There is currently no requirement for:

* Kubernetes
* GPU infrastructure
* Dedicated vector database
* Message queue
* Redis cluster

This keeps the system appropriate for a portfolio-scale production deployment while maintaining a clear path for future scaling.

---

# Frontend

The original application was implemented as a Streamlit prototype.

The frontend was rebuilt using React + TypeScript + Vite.

The current UI provides dedicated components for:

* Prompt input
* Analysis mode selection
* Generated answer
* Reliability summary
* Claim-level results
* Evidence
* Verification breakdown
* Performance information
* Backend health status
* Loading states
* Error states

Generated Markdown is rendered properly in the UI, so model output such as:

```markdown
**Original height:** 300 meters
```

is displayed as formatted text instead of exposing Markdown syntax to the user.

---

# API

## Health Check

```http
GET /health
```

Example:

```json
{
  "status": "ok"
}
```

This endpoint is used by the frontend to determine whether the backend is reachable.

---

## Ask & Verify

```http
POST /ask
```

Request:

```json
{
  "prompt": "When was the Eiffel Tower built, and how tall is it?",
  "mode": "deep"
}
```

Supported modes:

```text
quick
standard
deep
```

The endpoint generates an answer and runs the verification pipeline against the resulting claims.

---

# Verification Pipeline

The current verification flow is approximately:

```text
1. Receive user prompt
        ↓
2. Generate AI answer
        ↓
3. Extract factual claims
        ↓
4. Retrieve local semantic evidence
        ↓
5. Retrieve web evidence
        ↓
6. Verify claims against evidence
        ↓
7. Calculate verification signals
        ↓
8. Aggregate results
        ↓
9. Return structured response
        ↓
10. Render explanation in frontend
```

The architecture is intentionally modular so that individual verification strategies can be improved independently.

---

# Reliability Scoring

The project combines several signals when producing the overall reliability analysis.

These include signals related to:

* Factual evidence
* Logical consistency
* Citation presence
* Confidence language
* Cross-checking / consistency

The resulting score should be interpreted as a **heuristic reliability indicator**, not as a calibrated probability that an answer is hallucinated.

This distinction is important because a numerical score without a representative benchmark dataset and calibration procedure should not be presented as a scientifically validated probability.

---

# Performance Considerations

LLM and web-based verification introduces latency because the request may involve several external operations.

Potential latency sources include:

* Answer generation
* Claim extraction
* Embedding requests
* Web search
* Verification model calls
* Network latency
* Render cold starts

The frontend therefore exposes performance information rather than hiding the fact that verification is a multi-stage process.

Future optimization areas include:

* Parallel claim verification
* Request caching
* Embedding caching
* Search-result caching
* Reducing unnecessary LLM calls
* Batch embedding
* Per-stage latency instrumentation
* Async processing where appropriate

---

# Security Considerations

Security was considered at both the frontend and backend levels.

## Secrets

API keys are stored using environment variables.

Never commit:

```text
GEMINI_API_KEY
```

or other credentials to Git.

---

## CORS

Production CORS origins should be explicitly configured through:

```text
ALLOWED_ORIGINS
```

rather than allowing arbitrary browser origins.

---

## Input Validation

The FastAPI API uses Pydantic models to validate request structure before processing.

Input limits should also be maintained as the application evolves to prevent unnecessarily large prompts from consuming excessive API resources.

---

## Network Reliability

External service calls can fail independently.

The application therefore handles:

* API failures
* Network failures
* Timeouts
* Invalid responses
* Backend errors

rather than assuming every external dependency is always available.

---

## Logging

Sensitive credentials and unnecessary user content should not be written to logs.

Debug logging in the frontend is intended for development and troubleshooting and should be reviewed before production-scale usage.

---

## Prompt Injection

Because the system retrieves external evidence and passes content between multiple LLM stages, prompt injection is an important future security consideration.

Retrieved web content should be treated as **untrusted data**, not as instructions.

A future hardened implementation should:

* Separate evidence from system instructions
* Clearly delimit retrieved content
* Instruct verification models to treat evidence as data
* Prevent retrieved text from changing the verification task
* Sanitize or constrain external content where appropriate

---

# Current Limitations

This project is a production-oriented portfolio implementation, not a fully validated commercial hallucination detection platform.

Important limitations include:

### 1. Heuristic Scoring

The overall reliability score currently combines heuristic signals.

It is not a calibrated probability.

---

### 2. Small Local Knowledge Base

The local vector store is intentionally lightweight and currently contains a small set of documents.

A production system handling large document collections would benefit from a persistent vector database.

Potential future options include:

* PostgreSQL + pgvector
* Qdrant
* Weaviate
* Pinecone

---

### 3. Web Evidence Quality

Search results are not equivalent to authoritative sources.

A stronger production implementation would:

* Retrieve source URLs
* Rank source quality
* Extract relevant passages
* Check source credibility
* Detect conflicting sources
* Show direct supporting evidence for each claim

---

### 4. Verification Is Not Ground Truth

An LLM verifier can itself make mistakes.

Therefore:

```text
LLM-generated answer
        ↓
LLM-based verification
```

does not guarantee correctness.

The system is designed to make verification more transparent by combining model judgments with retrieved evidence.

---

### 5. No Scientific Accuracy Claim

The application should not claim a definitive hallucination-detection accuracy without a reproducible benchmark dataset, labeling methodology, evaluation protocol, and held-out test set.

Future evaluation should include metrics such as:

* Precision
* Recall
* F1
* ROC-AUC
* Calibration
* False-positive rate
* False-negative rate
* Claim-level accuracy

---

# Testing

The backend includes automated tests covering core application behavior.

Tests should be run locally with:

```bash
pytest
```

Python syntax can be checked with:

```bash
python -m compileall .
```

Frontend production build:

```bash
npm run build
```

---

# Local Development

## Backend

Clone the repository:

```bash
git clone https://github.com/Shreyabhat11/ai-hallucination-detector.git
cd ai-hallucination-detector
```

Create a Python environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
GEMINI_API_KEY=your_api_key_here
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174
WEB_SEARCH_MAX_RESULTS=8
WEB_SEARCH_RETRIES=1
WEB_SEARCH_TIMEOUT_SECONDS=8
WEB_PAGE_FETCH_LIMIT=3
WEB_PAGE_TIMEOUT_SECONDS=5
WEB_PAGE_MAX_BYTES=1000000
WEB_PAGE_MAX_REDIRECTS=3
WEB_PAGE_MAX_TEXT_CHARS=12000
```

Web search can request up to eight results per query and attempts bounded webpage extraction for up to three results. Fetching checks each robots.txt policy and falls back to the search-result excerpt if a page is disallowed, unavailable, or fails URL, content-type, timeout, or size checks. Publisher, author, and publication dates are displayed only when returned by the source; these metadata are not a validated credibility score.

Start the API:

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

The API will be available at:

```text
http://localhost:8001
```

API documentation:

```text
http://localhost:8001/docs
```

---

# Frontend Development

Move into the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Create:

```text
.env
```

with:

```env
VITE_API_BASE_URL=http://localhost:8001
```

Start the development server:

```bash
npm run dev
```

The Vite development server will provide the local frontend URL.

---

# Production Deployment

## Frontend — Vercel

The React/Vite frontend is deployed using Vercel.

Production environment variable:

```env
VITE_API_BASE_URL=https://ai-hallucination-detector-1.onrender.com
```

Build command:

```bash
npm run build
```

Output directory:

```text
dist
```

---

## Backend — Render

The FastAPI backend is deployed on Render.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Required environment variables:

```text
GEMINI_API_KEY
ALLOWED_ORIGINS
```

Example:

```text
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174,https://your-frontend.vercel.app
```

---

# Production Checklist

Before considering a deployment production-ready, verify:

* [x] Frontend deployed
* [x] Backend deployed
* [x] HTTPS enabled
* [x] API health endpoint available
* [x] Production frontend connected to backend
* [x] CORS configured
* [x] API secrets stored as environment variables
* [x] Frontend request timeout implemented
* [x] API error states handled
* [x] Production frontend build succeeds
* [x] Heavy local embedding model removed
* [x] API documentation available
* [x] Automated tests available
* [ ] Rate limiting
* [ ] Authentication / authorization
* [ ] Persistent vector database
* [ ] Centralized structured logging
* [ ] Monitoring and alerting
* [ ] Comprehensive benchmark dataset
* [ ] Score calibration
* [ ] Automated security scanning

The unchecked items represent areas for future hardening rather than features currently claimed by the application.

---

# Future Improvements

## Verification Quality

* Claim-to-evidence alignment
* Source quality scoring
* Contradiction detection
* Better citation validation
* Multi-source agreement
* Temporal validity checks
* Domain-specific verification

## Performance

* Parallel claim verification
* Async processing
* Embedding caching
* Search caching
* Reduced LLM calls
* Batch verification
* Per-stage latency metrics

## Data & Retrieval

* PDF/DOCX/TXT upload
* Persistent document storage
* PostgreSQL + pgvector
* Hybrid keyword + semantic retrieval
* Reranking
* Document metadata filtering

## Evaluation

Build a labeled hallucination benchmark containing:

```text
Prompt
Generated Answer
Individual Claim
Ground Truth
Supporting Evidence
Expected Verification
```

Then measure:

```text
Precision
Recall
F1
ROC-AUC
Calibration
False Positive Rate
False Negative Rate
```

This would allow the reliability score to evolve from a heuristic into an empirically calibrated signal.

## Security

* Rate limiting
* Authentication
* Abuse prevention
* Request quotas
* Prompt-injection defenses
* Secure evidence isolation
* Dependency vulnerability scanning
* Structured audit logging

---

# Project Structure

```text
ai-hallucination-detector/
│
├── app/
│   ├── config.py
│   │
│   ├── detector/
│   │   ├── fact_check.py
│   │   ├── citation_check.py
│   │   ├── confidence.py
│   │   ├── cross_model.py
│   │   └── scoring.py
│   │
│   ├── llm/
│   │   ├── generator.py
│   │   └── verifier.py
│   │
│   ├── utils/
│   │   ├── embeddings.py
│   │   ├── similarity.py
│   │   └── web_search.py
│   │
│   └── vector_db/
│       └── simple_store.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── api/
│   │   ├── types/
│   │   └── ...
│   ├── package.json
│   └── vite.config.ts
│
├── tests/
│
├── main.py
├── requirements.txt
└── README.md
```

---

# Why This Project?

This project was built to explore a practical problem at the intersection of:

* Generative AI
* Retrieval-Augmented Generation
* Information retrieval
* LLM evaluation
* AI reliability
* API engineering
* Production deployment

The main engineering challenge is not simply generating an answer.

It is building a system that can answer:

> **"Why should I trust this claim?"**

That led to an architecture focused on claim-level analysis, evidence retrieval, and explainability rather than treating hallucination detection as a single opaque classification model.

---

# Author

**Shreya Bhat**

AI / ML Engineer | Data Scientist

GitHub: [https://github.com/Shreyabhat11](https://github.com/Shreyabhat11)

````

### A couple of things I'd change before you commit it

There are **two placeholders** I intentionally left rather than guessing:

```text
https://frontend-coral-one-6cme2r1fvt.vercel.app/
````
### Persistent history

Install dependencies, copy `.env.example` to `.env`, then initialize the configured
database with:

```powershell
python -m alembic upgrade head
```

SQLite is used by default (`DATABASE_URL=sqlite:///./hallucination_detector.db`).
Set `DATABASE_URL` to a PostgreSQL SQLAlchemy URL for deployment. Local history uses
the `local-user` owner unless `HISTORY_AUTH_REQUIRED=true`; authenticated deployments
must provide an authenticated `X-User-Id` boundary and replace this development
identity mechanism with real authentication before exposing private history.

History endpoints are `GET /api/history`, `GET /api/history/{analysisId}`,
`DELETE /api/history/{analysisId}`, `POST /api/history/delete`, and
`GET /api/analytics?days=7|30|90|180`. `/api/analyze` saves only when
`save_history` is enabled and stores input text only when `save_input_text` is enabled.
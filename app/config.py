import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "gemini-3.8-flash")
VERIFIER_MODEL = os.getenv("VERIFIER_MODEL", "gemini-3.1-flash-lite")

# --- Security / robustness settings -----------------------------------
# All overridable via env vars so the deployment's config doesn't require
# a code change.

# Comma-separated list of allowed origins for CORS. Defaults to the Vite
# dev server's origin -- deliberately NOT a wildcard. Set this to the
# actual deployed frontend URL (e.g. "https://your-frontend.vercel.app")
# via the ALLOWED_ORIGINS env var in the Render deployment's settings.
# Multiple origins: comma-separated, e.g.
#   ALLOWED_ORIGINS=http://localhost:5173,https://your-frontend.vercel.app
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:5174,https://frontend-coral-one-6cme2r1fvt.vercel.app",
    ).split(",") if o.strip()
]

# Sliding-window rate limit: N requests per WINDOW_SECONDS per client IP.
# In-process only (see app/utils/rate_limit.py) -- resets on restart, not
# shared across multiple workers/instances. Acceptable for a single-instance
# portfolio deployment; would need a shared store (e.g. Redis) to be correct
# behind multiple workers, which is intentionally not introduced here.
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "20"))
RATE_LIMIT_WINDOW_SECONDS = float(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# Reject request bodies larger than this before they're parsed.
MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(50 * 1024)))  # 50 KB

# Hard ceiling on total request processing time (generation + full
# pipeline). Prevents a pathological Deep-mode request (or an upstream
# hang not caught by the per-call timeouts) from holding a worker forever.
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "8"))
WEB_SEARCH_RETRIES = int(os.getenv("WEB_SEARCH_RETRIES", "1"))
WEB_SEARCH_TIMEOUT_SECONDS = float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "8"))
WEB_PAGE_FETCH_LIMIT = int(os.getenv("WEB_PAGE_FETCH_LIMIT", "3"))
WEB_PAGE_TIMEOUT_SECONDS = float(os.getenv("WEB_PAGE_TIMEOUT_SECONDS", "5"))
WEB_PAGE_MAX_BYTES = int(os.getenv("WEB_PAGE_MAX_BYTES", "1000000"))
WEB_PAGE_MAX_REDIRECTS = int(os.getenv("WEB_PAGE_MAX_REDIRECTS", "3"))
WEB_PAGE_MAX_TEXT_CHARS = int(os.getenv("WEB_PAGE_MAX_TEXT_CHARS", "12000"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hallucination_detector.db")
HISTORY_AUTH_REQUIRED = os.getenv("HISTORY_AUTH_REQUIRED", "false").lower() == "true"
KNOWLEDGE_BASE_PATH = os.getenv(
    "KNOWLEDGE_BASE_PATH", "app/vector_db/default_knowledge_base.jsonl"
)

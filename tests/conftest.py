import os

# Set before any app module is imported, since app.config / app.llm.* /
# app.utils.embeddings construct a genai.Client at import time. Tests never
# make real network calls to Gemini -- they monkeypatch the async wrapper
# functions -- so this key is never actually used to authenticate.
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")
os.environ.setdefault("PRIMARY_MODEL", "gemini-3.8-flash")
os.environ.setdefault("VERIFIER_MODEL", "models/gemini-3.1-flash-lite")

import asyncio
import logging

from google import genai

from app.config import GEMINI_API_KEY, PRIMARY_MODEL

logger = logging.getLogger(__name__)

client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

DEFAULT_TIMEOUT_S = 20.0


def generate_answer(prompt: str) -> str:
    """Synchronous call to the primary Gemini model. Kept for callers that
    aren't async (e.g. the KB loader). Prefer generate_answer_async in the
    request path.
    """
    if client is None:
        return "LLM Error: GEMINI_API_KEY is not configured"
    try:
        response = client.models.generate_content(model=PRIMARY_MODEL, contents=prompt)
        return response.text or ""
    except Exception as e:
        logger.warning("generate_answer failed: %s", e)
        return f"LLM Error: {str(e)}"


async def generate_answer_async(prompt: str, timeout: float = DEFAULT_TIMEOUT_S) -> str:
    """Runs the blocking SDK call in a thread so it doesn't block the event
    loop, with a hard timeout so a hung request can't stall the whole
    pipeline.
    """
    try:
        return await asyncio.wait_for(asyncio.to_thread(generate_answer, prompt), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("generate_answer_async timed out after %.1fs", timeout)
        return "LLM Error: generation timed out"

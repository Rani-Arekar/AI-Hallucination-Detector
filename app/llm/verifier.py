import asyncio
import logging

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, VERIFIER_MODEL

logger = logging.getLogger(__name__)

client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

DEFAULT_TIMEOUT_S = 15.0


def verify_prompt(prompt: str, system_instruction: str | None = None) -> str:
    if client is None:
        logger.warning("verify_prompt skipped because GEMINI_API_KEY is not configured")
        return "UNCERTAIN"
    try:
        config = (
            types.GenerateContentConfig(system_instruction=system_instruction)
            if system_instruction
            else None
        )
        response = client.models.generate_content(
            model=VERIFIER_MODEL, contents=prompt, config=config
        )
        return response.text or ""
    except Exception as e:
        logger.warning("verify_prompt failed: %s", e)
        return "UNCERTAIN"


async def verify_prompt_async(
    prompt: str, system_instruction: str | None = None, timeout: float = DEFAULT_TIMEOUT_S
) -> str:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(verify_prompt, prompt, system_instruction), timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.warning("verify_prompt_async timed out after %.1fs", timeout)
        return "UNCERTAIN"

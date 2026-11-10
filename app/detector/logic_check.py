from app.llm.verifier import verify_prompt, verify_prompt_async
from app.utils.prompt_safety import VERIFICATION_SYSTEM_INSTRUCTION, wrap_untrusted

_PROMPT_TEMPLATE = """
Does the following text contain internal contradictions?
Return only: YES or NO

{answer}
"""


def _score_logic_response(response: str) -> float:
    normalized = (response or "").strip().upper()
    if normalized == "YES":
        return 0.3
    if normalized == "NO":
        return 1.0
    return 0.5


def logic_score(answer: str) -> float:
    prompt = _PROMPT_TEMPLATE.format(answer=wrap_untrusted(answer))
    res = verify_prompt(prompt, system_instruction=VERIFICATION_SYSTEM_INSTRUCTION)
    return _score_logic_response(res)


async def logic_score_async(answer: str) -> float:
    prompt = _PROMPT_TEMPLATE.format(answer=wrap_untrusted(answer))
    res = await verify_prompt_async(prompt, system_instruction=VERIFICATION_SYSTEM_INSTRUCTION)
    return _score_logic_response(res)

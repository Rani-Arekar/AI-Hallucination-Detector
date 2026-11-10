import asyncio

from app.llm.generator import generate_answer_async

# NOTE ON NAMING: despite the module name (kept for now to avoid an
# API-breaking rename mid-refactor), this is a SAME-MODEL SELF-CONSISTENCY
# check -- it asks the same model the same prompt twice and compares the
# outputs. It is not genuine cross-model verification and should not be
# presented as such. A real redesign (independent claim-level verification,
# which fact_check.py now does, and/or an actual second provider) is planned
# for the verification-quality phase. Flagging this honestly here rather
# than silently leaving the old misleading name unexplained.


async def cross_model_score_async(prompt: str) -> float:
    a1, a2 = await asyncio.gather(
        generate_answer_async(prompt),
        generate_answer_async(prompt),
    )
    if a1.startswith("LLM Error:") or a2.startswith("LLM Error:"):
        return 0.5
    return 1.0 if a1 == a2 else 0.6

from unittest.mock import AsyncMock, patch

import pytest

from app.detector.cross_model import cross_model_score_async


@pytest.mark.asyncio
@patch("app.detector.cross_model.generate_answer_async", new_callable=AsyncMock)
async def test_generation_errors_do_not_count_as_self_consistency(mock_generate):
    mock_generate.return_value = "LLM Error: configured model unavailable"

    score = await cross_model_score_async("A factual question")

    assert score == 0.5
    assert mock_generate.await_count == 2
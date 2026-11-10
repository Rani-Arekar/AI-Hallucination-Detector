from unittest.mock import AsyncMock, patch

import pytest

from app.detector.logic_check import logic_score, logic_score_async


@pytest.mark.parametrize(
    ("response", "expected"),
    [("YES", 0.3), ("NO", 1.0), ("UNCERTAIN", 0.5), ("unexpected", 0.5), ("", 0.5)],
)
@patch("app.detector.logic_check.verify_prompt")
def test_logic_score_uses_exact_labels_and_neutral_fallback(mock_verify, response, expected):
    mock_verify.return_value = response

    assert logic_score("A statement.") == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(("response", "expected"), [("YES", 0.3), ("NO", 1.0), ("UNCERTAIN", 0.5)])
@patch("app.detector.logic_check.verify_prompt_async", new_callable=AsyncMock)
async def test_async_logic_score_uses_exact_labels(mock_verify, response, expected):
    mock_verify.return_value = response

    assert await logic_score_async("A statement.") == expected
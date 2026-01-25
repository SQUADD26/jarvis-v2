import pytest
from jarvis.core.orchestrator import process_message


@pytest.mark.asyncio
async def test_simple_greeting():
    response = await process_message("test_user", "ciao")
    assert response is not None
    assert len(response) > 0


@pytest.mark.asyncio
async def test_calendar_query():
    response = await process_message("test_user", "che impegni ho oggi")
    assert response is not None
    # Should mention calendar or events

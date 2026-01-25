import pytest
from jarvis.core.router import router


@pytest.fixture(autouse=True)
async def init_router():
    await router.initialize()


@pytest.mark.asyncio
async def test_calendar_read_intent():
    intent, confidence = await router.route("che impegni ho domani")
    assert intent == "calendar_read"
    assert confidence > 0.7


@pytest.mark.asyncio
async def test_email_read_intent():
    intent, confidence = await router.route("controlla le email")
    assert intent == "email_read"
    assert confidence > 0.7


@pytest.mark.asyncio
async def test_chitchat_intent():
    intent, confidence = await router.route("ciao come stai")
    assert intent == "chitchat"
    assert confidence > 0.7


@pytest.mark.asyncio
async def test_complex_intent():
    intent, confidence = await router.route("analizza i dati del trimestre e prepara un report")
    # Should be complex or low confidence
    assert intent == "complex" or confidence < 0.75

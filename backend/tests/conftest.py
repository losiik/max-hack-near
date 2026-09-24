import pytest
from httpx import ASGITransport, AsyncClient

from max_assist.config import settings
from max_assist.db import engine
from max_assist.main import app

settings.cleanup_enabled = False
settings.expiry_enabled = False


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    assert engine.pool.checkedout() == 0, "тест оставил соединение с базой открытым"
    await engine.dispose()

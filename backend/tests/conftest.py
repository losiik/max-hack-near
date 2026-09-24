import pytest
from httpx import ASGITransport, AsyncClient

from max_assist.db import engine
from max_assist.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await engine.dispose()

import pytest
from httpx import ASGITransport, AsyncClient

from max_assist.config import settings
from max_assist.db import engine
from max_assist.main import app
from max_assist.modules.voice.livekit import rooms

settings.cleanup_enabled = False
settings.expiry_enabled = False


class VoiceServer:
    def __init__(self):
        self.calls = []
        self.up = True

    def patch(self, monkeypatch):
        for name in ("open", "remove", "close"):
            monkeypatch.setattr(rooms, name, self.recorder(name))
        monkeypatch.setattr(rooms, "ping", self.ping)

    def recorder(self, name):
        async def call(*args):
            self.calls.append((name, *args))

        return call

    async def ping(self):
        return self.up

    def calls_for(self, room):
        return [call for call in self.calls if call[1] == str(room)]


@pytest.fixture(autouse=True)
def voice(monkeypatch):
    server = VoiceServer()
    server.patch(monkeypatch)
    return server


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    assert engine.pool.checkedout() == 0, "тест оставил соединение с базой открытым"
    await engine.dispose()

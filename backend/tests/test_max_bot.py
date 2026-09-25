import json
import logging
from uuid import uuid4

import httpx
import pytest

from max_assist.config import settings
from max_assist.modules.identity.models import User
from max_assist.modules.notifications import max_bot
from max_assist.modules.notifications import service as notifications

TOKEN = "bot-token-for-tests"


class FakeMax:
    def __init__(self, status=200, body=None, broken=False):
        self.status = status
        self.body = body if body is not None else {"username": "ryadom_bot", "is_bot": True}
        self.broken = broken
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.broken:
            raise httpx.ConnectError("max is unreachable", request=request)
        return httpx.Response(self.status, json=self.body)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=settings.max_api_base,
            transport=httpx.MockTransport(self.handle),
            headers={"Authorization": settings.max_bot_token},
        )

    def messages(self) -> list[httpx.Request]:
        return [item for item in self.requests if item.url.path == "/messages"]


@pytest.fixture
def max_server(monkeypatch):
    monkeypatch.setattr(settings, "max_bot_token", TOKEN)
    monkeypatch.setattr(max_bot, "username", None)
    notifications.outbox.clear()

    def install(server):
        monkeypatch.setattr(max_bot, "client", server.client)
        return server

    yield install
    notifications.outbox.clear()


def person(max_user_id=555):
    return User(id=uuid4(), first_name="Сергей", last_name="Клосеп", max_user_id=max_user_id)


async def test_bot_name_is_asked_at_startup_and_used_in_links(max_server):
    server = max_server(FakeMax())

    await max_bot.load_identity()

    assert max_bot.username == "ryadom_bot"
    assert server.requests[0].url.path == "/me"
    assert server.requests[0].headers["authorization"] == TOKEN
    assert notifications.app_link("as_abc") == "https://max.ru/ryadom_bot?startapp=as_abc"
    assert notifications.app_link() == "https://max.ru/ryadom_bot"


async def test_settings_name_is_used_until_the_bot_answers(max_server):
    max_server(FakeMax(status=401, body={"code": "unauthorized"}))

    await max_bot.load_identity()

    assert max_bot.username is None
    assert notifications.app_link("pr_1") == f"https://max.ru/{settings.max_bot_username}?startapp=pr_1"


async def test_invitation_goes_to_max_with_two_buttons(max_server):
    server = max_server(FakeMax())
    await max_bot.load_identity()
    helper = person()

    delivered = await notifications.help_requested(helper, "Людмила П.", "Компенсация ЖКУ", "Ab12")

    [request] = server.messages()
    body = json.loads(request.read())
    assert delivered is True
    assert request.method == "POST"
    assert dict(request.url.params) == {"user_id": "555"}
    assert body["text"] == "Людмила П. просит помочь с услугой «Компенсация ЖКУ»"
    assert body["notify"] is True
    [keyboard] = body["attachments"]
    assert keyboard["type"] == "inline_keyboard"
    assert keyboard["payload"]["buttons"] == [
        [{"type": "link", "text": "Подключиться", "url": "https://max.ru/ryadom_bot?startapp=as_Ab12"}],
        [{"type": "link", "text": "Сейчас не могу", "url": "https://max.ru/ryadom_bot?startapp=ad_Ab12"}],
    ]
    assert len(notifications.messages_for(helper.id)) == 1


async def test_client_talks_to_the_configured_api_with_the_token(monkeypatch):
    monkeypatch.setattr(settings, "max_bot_token", TOKEN)

    async with max_bot.client() as http:
        assert str(http.base_url) == settings.max_api_base
        assert http.headers["authorization"] == TOKEN


async def test_message_without_buttons_goes_without_a_keyboard(max_server):
    server = max_server(FakeMax())

    await notifications.send(person(), "Заявление сохранено", [])

    body = json.loads(server.messages()[0].read())
    assert "attachments" not in body


async def test_rejected_message_is_reported_as_not_delivered(max_server, caplog):
    max_server(FakeMax(status=403, body={"code": "forbidden"}))

    with caplog.at_level(logging.WARNING, logger="max_assist.notifications"):
        delivered = await notifications.help_requested(person(), "Людмила П.", "ЖКУ", "Ab12")

    assert delivered is False
    assert "bot message rejected" in caplog.text


async def test_unreachable_max_does_not_break_the_scenario(max_server, caplog):
    max_server(FakeMax(broken=True))

    with caplog.at_level(logging.ERROR, logger="max_assist.notifications"):
        delivered = await notifications.help_requested(person(), "Людмила П.", "ЖКУ", "Ab12")
        await max_bot.load_identity()

    assert delivered is False
    assert max_bot.username is None
    assert "bot message failed" in caplog.text
    assert "could not read bot profile" in caplog.text


async def test_people_without_max_account_get_only_the_dev_outbox(max_server):
    server = max_server(FakeMax())
    helper = person(max_user_id=None)

    delivered = await notifications.help_requested(helper, "Людмила П.", "ЖКУ", "Ab12")

    assert delivered is False
    assert server.messages() == []
    assert len(notifications.messages_for(helper.id)) == 1


async def test_without_a_token_nothing_is_sent(monkeypatch):
    monkeypatch.setattr(settings, "max_bot_token", "")
    sent = []
    monkeypatch.setattr(max_bot, "send", lambda *args: sent.append(args))

    delivered = await notifications.help_requested(person(), "Людмила П.", "ЖКУ", "Ab12")

    assert (delivered, sent) == (False, [])
    assert await max_bot.whoami() is None

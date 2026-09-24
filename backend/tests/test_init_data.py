import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from max_assist.config import settings
from max_assist.errors import Unauthorized
from max_assist.modules.identity.max_init_data import parse_init_data
from tests.helpers import forget_user

BOT_TOKEN = "123456:test-bot-token"
USER = {"id": 777, "first_name": "Людмила", "last_name": "Петрова"}


def sign(fields: dict[str, str], token: str = BOT_TOKEN) -> str:
    check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    return hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()


def build(token: str = BOT_TOKEN, **overrides) -> str:
    fields = {
        "query_id": "AAH1",
        "auth_date": str(int(time.time())),
        "user": json.dumps(USER, ensure_ascii=False),
        "start_param": "as_Ab12Cd34",
    }
    fields.update({key: value for key, value in overrides.items() if value is not None})
    return urlencode({**fields, "hash": sign(fields, token)})


def test_valid_init_data_is_accepted():
    payload = parse_init_data(build(), BOT_TOKEN, 86400)

    assert payload["user"]["id"] == 777
    assert payload["start_param"] == "as_Ab12Cd34"


def test_signature_made_with_another_token_is_rejected():
    raw = build(token="999999:someone-else")

    with pytest.raises(Unauthorized):
        parse_init_data(raw, BOT_TOKEN, 86400)


def test_tampered_user_is_rejected():
    raw = build()
    forged = json.dumps({"id": 1, "first_name": "Олег"}, ensure_ascii=False)
    raw = raw.replace(urlencode({"user": json.dumps(USER, ensure_ascii=False)}), urlencode({"user": forged}))

    with pytest.raises(Unauthorized):
        parse_init_data(raw, BOT_TOKEN, 86400)


def test_missing_hash_is_rejected():
    with pytest.raises(Unauthorized):
        parse_init_data(urlencode({"auth_date": str(int(time.time()))}), BOT_TOKEN, 86400)


def test_stale_init_data_is_rejected():
    raw = build(auth_date=str(int(time.time()) - 7200))

    with pytest.raises(Unauthorized):
        parse_init_data(raw, BOT_TOKEN, 3600)


def test_init_data_without_user_is_rejected():
    raw = build(user="{}")

    with pytest.raises(Unauthorized):
        parse_init_data(raw, BOT_TOKEN, 86400)


async def test_login_through_max_is_unavailable_without_bot_token(client):
    response = await client.post("/api/v1/auth/max", json={"init_data": build()})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "max_login_unavailable"


async def test_login_through_max_creates_user_and_keeps_profile_fresh(client, monkeypatch):
    monkeypatch.setattr(settings, "max_bot_token", BOT_TOKEN)
    await forget_user(max_user_id=USER["id"])

    first = await client.post("/api/v1/auth/max", json={"init_data": build()})
    renamed = json.dumps({**USER, "last_name": "Иванова"}, ensure_ascii=False)
    second = await client.post("/api/v1/auth/max", json={"init_data": build(user=renamed)})
    me = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {second.json()['access_token']}"},
    )

    assert first.status_code == 200
    assert first.json()["user"]["display_name"] == "Людмила П."
    assert second.json()["user"]["id"] == first.json()["user"]["id"]
    assert me.json()["last_name"] == "Иванова"


async def test_login_through_max_rejects_broken_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "max_bot_token", BOT_TOKEN)

    response = await client.post("/api/v1/auth/max", json={"init_data": build(token="another")})

    assert response.status_code == 401

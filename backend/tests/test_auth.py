from datetime import timedelta
from uuid import uuid4

import jwt

from max_assist.config import settings
from max_assist.modules.identity.models import User
from max_assist.utils import now
from tests.helpers import forget_user, login, start_session


def test_display_name_shortens_last_name():
    assert User(first_name="Сергей", last_name="Клосеп").display_name == "Сергей К."
    assert User(first_name="Олег", last_name=None).display_name == "Олег"


async def test_dev_login_creates_user_on_first_call(client):
    await forget_user(dev_key="oleg")

    created = await client.post("/api/v1/auth/dev-login", json={"user_key": "oleg"})
    again = await client.post("/api/v1/auth/dev-login", json={"user_key": "oleg"})

    assert created.status_code == 200
    assert created.json()["user"]["display_name"] == "Олег Н."
    assert created.json()["access_token"]
    assert again.json()["user"]["id"] == created.json()["user"]["id"]


async def test_dev_login_with_unknown_key_is_rejected(client):
    response = await client.post("/api/v1/auth/dev-login", json={"user_key": "nobody"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_dev_users_are_listed(client):
    response = await client.get("/api/v1/dev/users")

    keys = [item["user_key"] for item in response.json()]
    assert keys == ["ludmila", "sergey", "anna", "oleg"]


async def test_broken_token_is_rejected(client):
    response = await client.get("/api/v1/me", headers={"Authorization": "Bearer not-a-token"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_expired_token_is_rejected(client):
    token = jwt.encode(
        {"sub": str(uuid4()), "exp": now() - timedelta(hours=1)},
        settings.jwt_secret,
        algorithm="HS256",
    )

    response = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


async def test_token_of_deleted_user_is_rejected(client):
    token = jwt.encode(
        {"sub": str(uuid4()), "exp": now() + timedelta(hours=1)},
        settings.jwt_secret,
        algorithm="HS256",
    )

    response = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Пользователь не найден"


async def test_dev_endpoints_are_closed_outside_dev(client, monkeypatch):
    headers = await login(client, "oleg")
    monkeypatch.setattr(settings, "app_env", "prod")

    users = await client.get("/api/v1/dev/users")
    reset = await client.post("/api/v1/dev/reset", headers=headers)
    dev_login = await client.post("/api/v1/auth/dev-login", json={"user_key": "oleg"})

    assert users.status_code == 403
    assert reset.status_code == 403
    assert dev_login.status_code == 403


REVIEW_PASSWORD = "long-review-password-for-tests"


async def review_login(client, password=REVIEW_PASSWORD, login="review"):
    return await client.post("/api/v1/auth/review-login", json={"login": login, "password": password})


async def test_review_login_is_closed_without_password(client, monkeypatch):
    monkeypatch.setattr(settings, "review_password", "")
    closed = await review_login(client, password="")

    monkeypatch.setattr(settings, "review_password", "short")
    too_short = await review_login(client, password="short")

    assert closed.status_code == 403
    assert too_short.status_code == 403


async def test_review_login_checks_login_and_password(client, monkeypatch):
    monkeypatch.setattr(settings, "review_password", REVIEW_PASSWORD)

    wrong_password = await review_login(client, password="long-but-wrong-password")
    wrong_login = await review_login(client, login="ludmila")

    assert wrong_password.status_code == 401
    assert wrong_login.status_code == 401


async def test_review_login_works_in_production(client, monkeypatch):
    await forget_user(dev_key="review")
    monkeypatch.setattr(settings, "review_password", REVIEW_PASSWORD)
    monkeypatch.setattr(settings, "app_env", "prod")

    first = await review_login(client)
    again = await review_login(client)
    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {first.json()['access_token']}"})

    assert first.status_code == 200
    assert again.json()["user"]["id"] == first.json()["user"]["id"]
    assert me.json()["display_name"] == "Проверка Ж."


async def test_me_counts_drafts(client):
    headers = await login(client, "anna")
    await start_session(client, headers)

    response = await client.get("/api/v1/me", headers=headers)

    assert response.json()["counters"]["drafts"] == 1

import logging

import httpx

from max_assist.config import settings

logger = logging.getLogger("max_assist.notifications")

TIMEOUT = httpx.Timeout(5.0)

# имя бота спрашиваем у самого MAX при старте: из него собираются ссылки на mini app
username: str | None = None


def enabled() -> bool:
    return bool(settings.max_bot_token)


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.max_api_base,
        timeout=TIMEOUT,
        headers={"Authorization": settings.max_bot_token},
    )


async def whoami() -> str | None:
    if not enabled():
        return None
    try:
        async with client() as http:
            response = await http.get("/me")
        if response.status_code == 200:
            return response.json().get("username")
        logger.warning("bot profile request failed: %s %s", response.status_code, response.text[:200])
    except Exception:
        logger.exception("could not read bot profile")
    return None


async def load_identity() -> None:
    global username
    username = await whoami()
    if username:
        logger.info("bot is @%s", username)


async def send(max_user_id: int, text: str, buttons: list[dict]) -> bool:
    payload: dict = {"text": text, "notify": True}
    if buttons:
        # в MAX клавиатура — это вложение; каждая кнопка на своей строке
        payload["attachments"] = [
            {"type": "inline_keyboard", "payload": {"buttons": [[button] for button in buttons]}}
        ]

    try:
        async with client() as http:
            response = await http.post("/messages", params={"user_id": max_user_id}, json=payload)
        if response.status_code == 200:
            return True
        logger.warning("bot message rejected: %s %s", response.status_code, response.text[:200])
    except Exception:
        logger.exception("bot message failed")
    return False

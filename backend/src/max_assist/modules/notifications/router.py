import hmac
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel

from max_assist.config import settings
from max_assist.deps import CurrentUser
from max_assist.errors import Forbidden, Unauthorized
from max_assist.modules.notifications import service

router = APIRouter(tags=["notifications"])


class ButtonOut(BaseModel):
    text: str
    start_param: str | None


class BotMessageOut(BaseModel):
    id: UUID
    created_at: datetime
    text: str
    buttons: list[ButtonOut]


@router.get("/dev/outbox", response_model=list[BotMessageOut])
async def dev_outbox(user: CurrentUser) -> list[BotMessageOut]:
    if not settings.is_dev:
        raise Forbidden("Dev-режим отключён")
    return [
        BotMessageOut(
            id=message.id,
            created_at=message.created_at,
            text=message.text,
            buttons=[ButtonOut(text=item.text, start_param=item.start_param) for item in message.buttons],
        )
        for message in service.messages_for(user.id)
    ]


@router.post("/max/webhook", include_in_schema=False)
async def max_webhook(request: Request, x_max_bot_api_secret: str = Header("")) -> Response:
    # без секрета любой мог бы заставить бота писать чужим людям
    if not settings.max_webhook_secret:
        raise Forbidden("Webhook бота выключен")
    if not hmac.compare_digest(x_max_bot_api_secret, settings.max_webhook_secret):
        raise Unauthorized("Неверный секрет webhook")

    await service.on_bot_update(await request.json())
    return Response(status_code=200)

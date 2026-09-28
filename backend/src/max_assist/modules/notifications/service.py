import logging
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from max_assist.config import settings
from max_assist.modules.identity.models import User
from max_assist.modules.notifications import max_bot
from max_assist.utils import now

OUTBOX_SIZE = 20

logger = logging.getLogger("max_assist.notifications")


@dataclass
class Button:
    text: str
    start_param: str | None = None


@dataclass
class Message:
    text: str
    buttons: list[Button]
    id: UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=now)


# видно через /dev/outbox: так сценарий проверяется и без бота, и вместе с ним
outbox: dict[UUID, deque[Message]] = defaultdict(lambda: deque(maxlen=OUTBOX_SIZE))


def bot_username() -> str:
    return max_bot.username or settings.max_bot_username


def app_link(start_param: str | None = None) -> str:
    link = f"https://max.ru/{bot_username()}"
    return f"{link}?startapp={start_param}" if start_param else link


async def send(user: User, text: str, buttons: list[Button]) -> bool:
    outbox[user.id].appendleft(Message(text, buttons))
    logger.info("bot message for %s: %s", user.id, text)

    if not max_bot.enabled() or user.max_user_id is None:
        return False
    return await max_bot.send(user.max_user_id, text, [as_link(button) for button in buttons])


def as_link(button: Button) -> dict[str, str]:
    return {"type": "link", "text": button.text, "url": app_link(button.start_param)}


def messages_for(user_id: UUID) -> list[Message]:
    return list(outbox.get(user_id, []))


async def help_requested(helper: User, owner_name: str, service_title: str, token: str) -> bool:
    return await send(
        helper,
        f"{owner_name} просит помочь с услугой «{service_title}»",
        [Button("Подключиться", f"as_{token}"), Button("Сейчас не могу", f"ad_{token}")],
    )


async def helper_busy(owner: User, helper_name: str) -> None:
    await send(
        owner,
        f"{helper_name} сейчас не может помочь. Заявление сохранено — напишем, когда появится возможность",
        [Button("Открыть заявление", "home")],
    )


async def come_back_later(helper: User, owner_name: str, callback_id: UUID) -> None:
    await send(
        helper,
        f"Когда появится время, нажмите кнопку — {owner_name} сможет позвать вас снова",
        [Button("Теперь могу помочь", f"ar_{callback_id}")],
    )


async def helper_ready(owner: User, helper_name: str, service_title: str, callback_id: UUID) -> None:
    # без start_param ссылка открыла бы чат с ботом, а не mini app
    await send(
        owner,
        f"{helper_name} может помочь с услугой «{service_title}»",
        [Button("Позвать", f"oc_{callback_id}")],
    )


async def operator_requested(staff: User, owner_name: str, service_title: str) -> bool:
    return await send(
        staff,
        f"{owner_name} ждёт сотрудника МФЦ: услуга «{service_title}»",
        [Button("Открыть очередь", "oq")],
    )


WELCOME = (
    "Здравствуйте! Это «Рядом» — помощь с госуслугами. Откройте приложение и начните заявление, "
    "а если что-то непонятно, позовите близкого, сотрудника МФЦ или цифрового сотрудника"
)


def start_sender(update: dict) -> int | None:
    # кто нажал «Начать» или написал /start; остальные сообщения бот не разбирает
    kind = update.get("update_type")
    if kind == "bot_started":
        return (update.get("user") or {}).get("user_id")
    if kind == "message_created":
        message = update.get("message") or {}
        text = ((message.get("body") or {}).get("text") or "").strip()
        if text.split(maxsplit=1)[:1] == ["/start"]:
            return (message.get("sender") or {}).get("user_id")
    return None


async def on_bot_update(update: dict) -> bool:
    max_user_id = start_sender(update)
    if max_user_id is None or not max_bot.enabled():
        return False
    return await max_bot.send(max_user_id, WELCOME, [as_link(Button("Открыть приложение", "home"))])

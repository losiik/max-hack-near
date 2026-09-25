import logging
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

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


# пока бота нет, сообщения остаются здесь, и их видно через /dev/outbox
outbox: dict[UUID, deque[Message]] = defaultdict(lambda: deque(maxlen=OUTBOX_SIZE))


def send(user_id: UUID, text: str, buttons: list[Button]) -> None:
    outbox[user_id].appendleft(Message(text, buttons))
    logger.info("bot message for %s: %s", user_id, text)


def messages_for(user_id: UUID) -> list[Message]:
    return list(outbox.get(user_id, []))


def help_requested(helper_id: UUID, owner_name: str, service_title: str, token: str) -> None:
    send(
        helper_id,
        f"{owner_name} просит помочь с услугой «{service_title}»",
        [Button("Подключиться", f"as_{token}"), Button("Сейчас не могу", f"ad_{token}")],
    )


def helper_busy(owner_id: UUID, helper_name: str) -> None:
    send(
        owner_id,
        f"{helper_name} сейчас не может помочь. Заявление сохранено — напишем, когда появится возможность",
        [Button("Открыть заявление")],
    )


def come_back_later(helper_id: UUID, owner_name: str, callback_id: UUID) -> None:
    send(
        helper_id,
        f"Когда появится время, нажмите кнопку — {owner_name} сможет позвать вас снова",
        [Button("Теперь могу помочь", f"ar_{callback_id}")],
    )


def helper_ready(owner_id: UUID, helper_name: str, service_title: str) -> None:
    send(
        owner_id,
        f"{helper_name} может помочь с услугой «{service_title}»",
        [Button("Позвать")],
    )

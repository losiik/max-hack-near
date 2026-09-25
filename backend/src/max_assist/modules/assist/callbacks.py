import uuid
from datetime import timedelta

from max_assist.config import settings
from max_assist.errors import Conflict
from max_assist.modules.assist.models import HelpCallback
from max_assist.utils import now

OPEN_STATUSES = {"busy", "ready"}


def is_open(callback: HelpCallback) -> bool:
    return callback.status in OPEN_STATUSES and callback.expires_at > now()


def require_open(callback: HelpCallback) -> None:
    if not is_open(callback):
        raise Conflict("help_callback_closed", "Это уже неактуально")


def promise(
    existing: HelpCallback | None,
    owner_id: uuid.UUID,
    helper_id: uuid.UUID,
    service_session_id: uuid.UUID,
) -> HelpCallback:
    moment = now()
    callback = existing or HelpCallback(
        id=uuid.uuid4(),
        owner_id=owner_id,
        helper_id=helper_id,
        service_session_id=service_session_id,
        created_at=moment,
    )
    callback.status = "busy"
    callback.ready_at = None
    callback.expires_at = moment + timedelta(days=settings.help_callback_ttl_days)
    return callback


def mark_ready(callback: HelpCallback) -> None:
    require_open(callback)
    if callback.status != "ready":
        callback.status = "ready"
        callback.ready_at = now()


def close(callback: HelpCallback, status: str) -> None:
    callback.status = status
    callback.closed_at = now()

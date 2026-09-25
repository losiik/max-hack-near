import logging
from datetime import timedelta

from sqlalchemy import delete, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.config import settings
from max_assist.db import session_factory
from max_assist.modules.applications.models import ServiceSession, ServiceSessionInbox
from max_assist.modules.assist.models import AssistInvite, HelpCallback
from max_assist.tasks import repeat
from max_assist.utils import now

logger = logging.getLogger("max_assist.maintenance")


async def cleanup(db: AsyncSession) -> dict[str, int]:
    moment = now()
    statements = {
        "inbox": delete(ServiceSessionInbox).where(
            ServiceSessionInbox.created_at < moment - timedelta(hours=settings.retention_inbox_hours)
        ),
        "invites": delete(AssistInvite).where(
            AssistInvite.created_at < moment - timedelta(days=settings.retention_invites_days)
        ),
        "help_callbacks": delete(HelpCallback).where(
            or_(
                HelpCallback.closed_at < moment - timedelta(days=settings.retention_callbacks_days),
                HelpCallback.expires_at < moment - timedelta(days=settings.retention_callbacks_days),
            )
        ),
        "drafts": delete(ServiceSession).where(
            ServiceSession.status.in_(["draft", "cancelled"]),
            ServiceSession.updated_at < moment - timedelta(days=settings.retention_drafts_days),
        ),
        "submitted": delete(ServiceSession).where(
            ServiceSession.status == "submitted",
            ServiceSession.submitted_at < moment - timedelta(days=settings.retention_submitted_days),
        ),
    }

    removed = {}
    for name, statement in statements.items():
        result = await db.execute(statement)
        removed[name] = result.rowcount or 0
    await db.commit()
    return removed


async def database_size_mb(db: AsyncSession) -> int:
    size = await db.scalar(text("select pg_database_size(current_database())"))
    return size // (1024 * 1024)


async def run_once() -> None:
    async with session_factory() as db:
        removed = await cleanup(db)
        size = await database_size_mb(db)

    if any(removed.values()):
        logger.info("cleanup removed %s", removed)
    if size > settings.db_size_warning_mb:
        logger.warning("database takes %s MB, limit is %s MB", size, settings.db_size_warning_mb)


async def run_forever() -> None:
    await repeat(run_once, lambda: settings.cleanup_interval_minutes * 60, "cleanup", logger)

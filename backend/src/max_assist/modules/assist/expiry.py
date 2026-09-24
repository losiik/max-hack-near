import logging

from max_assist.config import settings
from max_assist.db import session_factory
from max_assist.modules.assist import commands, service
from max_assist.tasks import repeat

logger = logging.getLogger("max_assist.assist")


async def run_once() -> None:
    async with session_factory() as db:
        expired = await service.expire_idle(db)
    commands.prune_limits()
    if expired:
        logger.info("expired %s idle assist sessions", expired)


async def run_forever() -> None:
    await repeat(run_once, lambda: settings.expiry_interval_seconds, "expiry", logger)

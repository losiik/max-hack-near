import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

background_tasks: set[asyncio.Task] = set()


def run_in_background(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task


async def uncancellable(coro: Coroutine[Any, Any, Any]) -> Any:
    # если задачу отменят посреди запроса к базе, работа доделается и вернёт соединение в пул
    return await asyncio.shield(run_in_background(coro))


async def wait_background() -> None:
    await asyncio.gather(*list(background_tasks), return_exceptions=True)


async def repeat(
    job: Callable[[], Coroutine[Any, Any, Any]],
    interval_seconds: Callable[[], float],
    name: str,
    logger: logging.Logger,
) -> None:
    while True:
        try:
            await uncancellable(job())
        except Exception:
            logger.exception("%s failed", name)
        await asyncio.sleep(interval_seconds())

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from max_assist import maintenance, tasks
from max_assist.config import settings
from max_assist.db import engine, session_factory
from max_assist.errors import register_error_handlers
from max_assist.modules.applications import service as applications_service
from max_assist.modules.applications.router import router as applications_router
from max_assist.modules.assist import events as assist_events
from max_assist.modules.assist import expiry, form_sync
from max_assist.modules.assist.router import router as assist_router
from max_assist.modules.assist.ws import router as assist_ws_router
from max_assist.modules.catalog.router import router as catalog_router
from max_assist.modules.identity.router import router as identity_router
from max_assist.modules.notifications import max_bot
from max_assist.modules.notifications.router import router as notifications_router
from max_assist.modules.support_desk import sync as support_sync
from max_assist.modules.support_desk.router import router as support_router
from max_assist.modules.trust.router import router as trust_router
from max_assist.modules.voice import recordings
from max_assist.modules.voice import sync as voice_sync
from max_assist.modules.voice.livekit import rooms
from max_assist.modules.voice.router import router as voice_router

app_logger = logging.getLogger("max_assist")
if not app_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s - %(message)s"))
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)

if form_sync.on_application_changed not in applications_service.listeners:
    applications_service.listeners.append(form_sync.on_application_changed)
applications_service.active_assist_lookup = form_sync.active_assist_id
for listener in (voice_sync.on_published, support_sync.on_published):
    if listener not in assist_events.listeners:
        assist_events.listeners.append(listener)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await max_bot.load_identity()
    loops = []
    if settings.cleanup_enabled:
        loops.append(asyncio.create_task(maintenance.run_forever()))
    if settings.expiry_enabled:
        loops.append(asyncio.create_task(expiry.run_forever()))
    yield
    for loop in loops:
        loop.cancel()
    await asyncio.gather(*loops, return_exceptions=True)
    await tasks.wait_background()
    await engine.dispose()


app = FastAPI(title="Рядом", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

api = APIRouter(prefix="/api/v1")
api.include_router(identity_router)
api.include_router(catalog_router)
api.include_router(applications_router)
api.include_router(assist_router)
api.include_router(notifications_router)
api.include_router(voice_router)
api.include_router(support_router)
api.include_router(trust_router)
app.include_router(api)
app.include_router(assist_ws_router)


@app.get("/health")
async def health() -> dict[str, str | int]:
    async with session_factory() as db:
        size = await maintenance.database_size_mb(db)
    voice = await rooms.ping()
    status = "ok" if size <= settings.db_size_warning_mb and voice else "degraded"
    return {
        "status": status,
        "db": "ok",
        "db_size_mb": size,
        "livekit": "ok" if voice else "down",
        "recordings_size_mb": recordings.folder_size_mb(),
    }

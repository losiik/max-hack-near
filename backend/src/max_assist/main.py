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
from max_assist.modules.assist import expiry, form_sync
from max_assist.modules.assist.router import router as assist_router
from max_assist.modules.assist.ws import router as assist_ws_router
from max_assist.modules.catalog.router import router as catalog_router
from max_assist.modules.identity.router import router as identity_router
from max_assist.modules.notifications.router import router as notifications_router

app_logger = logging.getLogger("max_assist")
if not app_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s - %(message)s"))
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)

if form_sync.on_application_changed not in applications_service.listeners:
    applications_service.listeners.append(form_sync.on_application_changed)
applications_service.active_assist_lookup = form_sync.active_assist_id


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
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
app.include_router(api)
app.include_router(assist_ws_router)


@app.get("/health")
async def health() -> dict[str, str | int]:
    async with session_factory() as db:
        size = await maintenance.database_size_mb(db)
    status = "ok" if size <= settings.db_size_warning_mb else "degraded"
    return {"status": status, "db": "ok", "db_size_mb": size}

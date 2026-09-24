from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from max_assist.config import settings
from max_assist.db import engine
from max_assist.errors import register_error_handlers
from max_assist.modules.applications.router import router as applications_router
from max_assist.modules.catalog.router import router as catalog_router
from max_assist.modules.identity.router import router as identity_router

app = FastAPI(title="Рядом", version="0.1.0")

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
app.include_router(api)


@app.get("/health")
async def health() -> dict[str, str]:
    async with engine.connect() as connection:
        await connection.execute(text("select 1"))
    return {"status": "ok", "db": "ok"}

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from max_assist.deps import CurrentUser, DbSession
from max_assist.modules.catalog import service

router = APIRouter(tags=["catalog"])


class ServiceSummaryOut(BaseModel):
    code: str
    version: int
    title: str
    short_description: str
    estimated_minutes: int
    steps_count: int
    is_demo: bool


@router.get("/services", response_model=list[ServiceSummaryOut])
async def list_services(user: CurrentUser, session: DbSession) -> list[ServiceSummaryOut]:
    rows = await service.list_services(session)
    return [
        ServiceSummaryOut(
            code=row.code,
            version=row.version,
            title=row.title,
            short_description=row.short_description,
            estimated_minutes=row.estimated_minutes,
            steps_count=row.steps_count,
            is_demo=row.is_demo,
        )
        for row in rows
    ]


@router.get("/services/{code}")
async def get_service(code: str, user: CurrentUser, session: DbSession) -> dict[str, Any]:
    definition = await service.load_definition(session, code)
    return definition.public_dict()

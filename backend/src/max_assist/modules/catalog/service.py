from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.errors import NotFound
from max_assist.modules.catalog.models import Service
from max_assist.modules.catalog.schema import ServiceDefinition

_definitions: dict[tuple[str, int], ServiceDefinition] = {}


async def list_services(session: AsyncSession) -> list[Service]:
    query = select(Service).where(Service.is_published.is_(True)).order_by(Service.title)
    return list(await session.scalars(query))


async def load_definition(
    session: AsyncSession,
    code: str,
    version: int | None = None,
) -> ServiceDefinition:
    if version is not None and (code, version) in _definitions:
        return _definitions[(code, version)]

    query = select(Service).where(Service.code == code, Service.is_published.is_(True))
    if version is None:
        query = query.order_by(Service.version.desc()).limit(1)
    else:
        query = query.where(Service.version == version)

    row = await session.scalar(query)
    if row is None:
        raise NotFound("Услуга не найдена")

    definition = ServiceDefinition.model_validate(row.definition)
    _definitions[(definition.code, definition.version)] = definition
    return definition

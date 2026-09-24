from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.db import session_factory
from max_assist.errors import Unauthorized
from max_assist.modules.identity.models import User
from max_assist.security import read_access_token
from max_assist.utils import now

bearer = HTTPBearer(auto_error=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise Unauthorized()

    user = await session.get(User, read_access_token(credentials.credentials))
    if user is None:
        raise Unauthorized("Пользователь не найден")

    user.last_seen_at = now()
    await session.commit()
    return user


DbSession = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]

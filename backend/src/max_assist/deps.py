from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.db import session_factory
from max_assist.errors import Unauthorized
from max_assist.modules.identity.models import User
from max_assist.security import AgentPass, read_access_token, read_agent_token
from max_assist.utils import now

bearer = HTTPBearer(auto_error=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def load_user(session: AsyncSession, token: str) -> User:
    user = await session.get(User, read_access_token(token))
    if user is None:
        raise Unauthorized("Пользователь не найден")
    return user


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise Unauthorized()

    user = await load_user(session, credentials.credentials)
    user.last_seen_at = now()
    await session.commit()
    return user


async def get_listener(
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    token: str | None = None,
) -> User:
    # тег <audio> не умеет передавать заголовки, поэтому токен можно положить в адрес
    if credentials is not None:
        return await load_user(session, credentials.credentials)
    if token is not None:
        return await load_user(session, token)
    raise Unauthorized()


async def get_caller(
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User | AgentPass:
    # некоторые запросы делает и человек, и цифровой сотрудник со своим токеном
    if credentials is None:
        raise Unauthorized()
    agent = read_agent_token(credentials.credentials)
    if agent is not None:
        return agent
    return await get_current_user(session, credentials)


async def get_agent(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AgentPass:
    agent = read_agent_token(credentials.credentials) if credentials else None
    if agent is None:
        raise Unauthorized("Нужен токен цифрового сотрудника")
    return agent


DbSession = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Listener = Annotated[User, Depends(get_listener)]
Caller = Annotated[User | AgentPass, Depends(get_caller)]
CurrentAgent = Annotated[AgentPass, Depends(get_agent)]

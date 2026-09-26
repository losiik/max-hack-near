from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

import jwt

from max_assist.config import settings
from max_assist.errors import Unauthorized
from max_assist.utils import now


def create_access_token(user_id: UUID) -> tuple[str, datetime]:
    expires_at = now() + timedelta(hours=settings.jwt_ttl_hours)
    token = jwt.encode(
        {"sub": str(user_id), "exp": expires_at},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return token, expires_at


@dataclass
class AgentPass:
    participant_id: UUID
    assist_session_id: UUID


def decode(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise Unauthorized("Сессия истекла, войдите снова") from exc


def read_access_token(token: str) -> UUID:
    payload = decode(token)
    # токеном агента нельзя войти как пользователь
    if payload.get("typ") == "agent":
        raise Unauthorized("Сессия истекла, войдите снова")
    try:
        return UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise Unauthorized("Сессия истекла, войдите снова") from exc


def create_agent_token(participant_id: UUID, assist_id: UUID) -> str:
    expires_at = now() + timedelta(hours=settings.agent_token_ttl_hours)
    return jwt.encode(
        {"sub": str(participant_id), "sid": str(assist_id), "typ": "agent", "exp": expires_at},
        settings.jwt_secret,
        algorithm="HS256",
    )


def read_agent_token(token: str) -> AgentPass | None:
    payload = decode(token)
    if payload.get("typ") != "agent":
        return None
    try:
        return AgentPass(participant_id=UUID(payload["sub"]), assist_session_id=UUID(payload["sid"]))
    except (KeyError, ValueError) as exc:
        raise Unauthorized("Сессия истекла, войдите снова") from exc

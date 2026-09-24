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


def read_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise Unauthorized("Сессия истекла, войдите снова") from exc

import hashlib
import hmac
import json
from typing import Any
from urllib.parse import parse_qsl

from max_assist.errors import Unauthorized
from max_assist.utils import now


def parse_init_data(raw: str, bot_token: str, max_age_seconds: int) -> dict[str, Any]:
    fields = dict(parse_qsl(raw, keep_blank_values=True))
    received_hash = fields.pop("hash", "")
    if not received_hash:
        raise Unauthorized("В данных запуска нет подписи")

    check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise Unauthorized("Неверная подпись данных запуска")

    auth_date = int(fields.get("auth_date") or 0)
    if now().timestamp() - auth_date > max_age_seconds:
        raise Unauthorized("Данные запуска устарели, откройте приложение снова")

    user = json.loads(fields.get("user") or "{}")
    if not user.get("id"):
        raise Unauthorized("В данных запуска нет пользователя")

    return {"user": user, "start_param": fields.get("start_param")}

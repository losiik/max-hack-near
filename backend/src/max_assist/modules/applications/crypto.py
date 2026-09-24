import json
from typing import Any

from cryptography.fernet import Fernet

from max_assist.config import settings

_fernet = Fernet(settings.field_encryption_key.encode())


def encrypt_values(values: dict[str, Any]) -> bytes | None:
    if not values:
        return None
    return _fernet.encrypt(json.dumps(values, ensure_ascii=False).encode())


def decrypt_values(blob: bytes | None) -> dict[str, Any]:
    if not blob:
        return {}
    return json.loads(_fernet.decrypt(bytes(blob)))

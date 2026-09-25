import hashlib
import secrets
import uuid
from datetime import timedelta

from max_assist.errors import Conflict, Forbidden, Gone, Unprocessable
from max_assist.modules.identity.models import User
from max_assist.modules.trust.models import Pairing, TrustedHelper
from max_assist.utils import now

TTL = {"qr": timedelta(minutes=5), "link": timedelta(hours=24)}
# владелец отвечает на «это ваш близкий?» не дольше 10 минут
ANSWER_TTL = timedelta(minutes=10)
MAX_TRUSTED = 5
ALIAS_LIMIT = 40
VERIFICATION = {"qr": "qr", "link": "invite_link"}


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_pairing(owner: User, method: str) -> tuple[Pairing, str]:
    token = secrets.token_urlsafe(24)
    moment = now()
    pairing = Pairing(
        id=uuid.uuid4(),
        owner_id=owner.id,
        method=method,
        token_hash=hash_token(token),
        status="pending",
        created_at=moment,
        expires_at=moment + TTL[method],
    )
    return pairing, token


def status_of(pairing: Pairing) -> str:
    moment = now()
    if pairing.status == "pending" and pairing.expires_at <= moment:
        return "expired"
    if pairing.status == "claimed" and pairing.claimed_at + ANSWER_TTL <= moment:
        return "expired"
    return pairing.status


def preview_status(pairing: Pairing, user: User, already_trusted: bool) -> str:
    status = status_of(pairing)
    if status == "expired":
        return "expired"
    if status != "pending":
        return "used"
    if user.id == pairing.owner_id:
        return "self"
    if already_trusted:
        return "already_trusted"
    return "valid"


def claim(pairing: Pairing, user: User, already_trusted: bool) -> None:
    status = preview_status(pairing, user, already_trusted)
    if status == "expired":
        raise Gone("pairing_expired", "Код устарел, попросите показать новый")
    if status == "used":
        raise Conflict("pairing_used", "Этот код уже использован")
    if status == "self":
        raise Unprocessable("pairing_self", "Нельзя добавить в близкие самого себя")
    if status == "already_trusted":
        raise Conflict("already_trusted", "Вы уже в списке близких")

    pairing.status = "claimed"
    pairing.claimed_by = user.id
    pairing.claimed_at = now()


def require_owner(pairing: Pairing, user: User) -> None:
    if pairing.owner_id != user.id:
        raise Forbidden("Это не ваш код")


def require_claimed(pairing: Pairing) -> None:
    status = status_of(pairing)
    if status == "expired":
        raise Gone("pairing_expired", "Время на подтверждение вышло")
    if status != "claimed":
        raise Conflict("pairing_not_claimed", "Код ещё никто не отсканировал")


def confirm(pairing: Pairing, owner: User, active_count: int, alias: str | None) -> TrustedHelper:
    require_owner(pairing, owner)
    require_claimed(pairing)
    if active_count >= MAX_TRUSTED:
        raise Conflict("trusted_limit_reached", f"Близких может быть не больше {MAX_TRUSTED}")

    pairing.status = "confirmed"
    pairing.resolved_at = now()
    return TrustedHelper(
        id=uuid.uuid4(),
        owner_id=owner.id,
        helper_id=pairing.claimed_by,
        alias=clean_alias(alias),
        status="active",
        verification_method=VERIFICATION[pairing.method],
        pairing_id=pairing.id,
        created_at=now(),
    )


def reject(pairing: Pairing, owner: User) -> None:
    require_owner(pairing, owner)
    require_claimed(pairing)
    pairing.status = "rejected"
    pairing.resolved_at = now()


def cancel(pairing: Pairing, owner: User) -> None:
    require_owner(pairing, owner)
    if status_of(pairing) in ("pending", "claimed"):
        pairing.status = "cancelled"
        pairing.resolved_at = now()


def clean_alias(alias: str | None) -> str | None:
    alias = (alias or "").strip() or None
    if alias is not None and len(alias) > ALIAS_LIMIT:
        raise Unprocessable("validation_error", f"Имя длиннее {ALIAS_LIMIT} символов")
    return alias


def rename(trusted: TrustedHelper, owner: User, alias: str | None) -> None:
    if trusted.owner_id != owner.id:
        raise Forbidden("Переименовать может только тот, кто добавил")
    trusted.alias = clean_alias(alias)


def revoke(trusted: TrustedHelper, user: User) -> None:
    if user.id not in (trusted.owner_id, trusted.helper_id):
        raise Forbidden("Это не ваша связь")
    trusted.status = "revoked"
    trusted.revoked_at = now()

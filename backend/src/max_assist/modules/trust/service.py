from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.errors import Conflict, NotFound
from max_assist.modules.identity.models import User
from max_assist.modules.trust import domain
from max_assist.modules.trust.models import Pairing, TrustedHelper


async def active_link(session: AsyncSession, owner_id: UUID, helper_id: UUID) -> TrustedHelper | None:
    return await session.scalar(
        select(TrustedHelper).where(
            TrustedHelper.owner_id == owner_id,
            TrustedHelper.helper_id == helper_id,
            TrustedHelper.status == "active",
        )
    )


async def is_trusted(session: AsyncSession, owner_id: UUID, helper_id: UUID) -> bool:
    return await active_link(session, owner_id, helper_id) is not None


async def my_helpers(session: AsyncSession, user: User) -> list[TrustedHelper]:
    query = (
        select(TrustedHelper)
        .where(TrustedHelper.owner_id == user.id, TrustedHelper.status == "active")
        .order_by(TrustedHelper.created_at)
    )
    return list(await session.scalars(query))


async def helping_for(session: AsyncSession, user: User) -> list[TrustedHelper]:
    query = (
        select(TrustedHelper)
        .where(TrustedHelper.helper_id == user.id, TrustedHelper.status == "active")
        .order_by(TrustedHelper.created_at)
    )
    return list(await session.scalars(query))


async def count_helpers(session: AsyncSession, user: User) -> int:
    return len(await my_helpers(session, user))


async def count_helping_for(session: AsyncSession, user: User) -> int:
    return len(await helping_for(session, user))


async def find_trusted(session: AsyncSession, user: User, trusted_id: UUID) -> TrustedHelper:
    trusted = await session.get(TrustedHelper, trusted_id, with_for_update=True)
    if trusted is None or trusted.status != "active" or user.id not in (trusted.owner_id, trusted.helper_id):
        raise NotFound("Близкий не найден")
    return trusted


async def own_helper(session: AsyncSession, owner: User, trusted_id: UUID) -> TrustedHelper:
    trusted = await session.get(TrustedHelper, trusted_id)
    if trusted is None or trusted.status != "active" or trusted.owner_id != owner.id:
        raise NotFound("Близкий не найден")
    return trusted


async def rename(session: AsyncSession, user: User, trusted_id: UUID, alias: str | None) -> TrustedHelper:
    trusted = await find_trusted(session, user, trusted_id)
    domain.rename(trusted, user, alias)
    await session.commit()
    return trusted


async def revoke(session: AsyncSession, user: User, trusted_id: UUID) -> None:
    trusted = await find_trusted(session, user, trusted_id)
    domain.revoke(trusted, user)
    await session.commit()


async def start_pairing(session: AsyncSession, user: User, method: str) -> tuple[Pairing, str]:
    pairing, token = domain.create_pairing(user, method)
    session.add(pairing)
    await session.commit()
    return pairing, token


async def own_pairing(session: AsyncSession, user: User, pairing_id: UUID) -> Pairing:
    pairing = await session.get(Pairing, pairing_id, with_for_update=True)
    if pairing is None or pairing.owner_id != user.id:
        raise NotFound("Код не найден")
    return pairing


async def by_token(session: AsyncSession, token: str) -> Pairing:
    pairing = await session.scalar(
        select(Pairing).where(Pairing.token_hash == domain.hash_token(token)).with_for_update()
    )
    if pairing is None:
        raise NotFound("Код не найден")
    return pairing


async def preview(session: AsyncSession, user: User, token: str) -> tuple[Pairing, str]:
    pairing = await by_token(session, token)
    status = domain.preview_status(pairing, user, await is_trusted(session, pairing.owner_id, user.id))
    return pairing, status


async def claim(session: AsyncSession, user: User, token: str) -> Pairing:
    pairing = await by_token(session, token)
    domain.claim(pairing, user, await is_trusted(session, pairing.owner_id, user.id))
    await session.commit()
    return pairing


async def confirm(session: AsyncSession, user: User, pairing_id: UUID, alias: str | None) -> TrustedHelper:
    pairing = await own_pairing(session, user, pairing_id)
    if pairing.claimed_by is not None and await is_trusted(session, user.id, pairing.claimed_by):
        raise Conflict("already_trusted", "Этот человек уже в списке близких")
    active_count = await session.scalar(
        select(func.count())
        .select_from(TrustedHelper)
        .where(TrustedHelper.owner_id == user.id, TrustedHelper.status == "active")
    )
    trusted = domain.confirm(pairing, user, active_count, alias)
    session.add(trusted)
    await session.commit()
    return trusted


async def reject(session: AsyncSession, user: User, pairing_id: UUID) -> Pairing:
    pairing = await own_pairing(session, user, pairing_id)
    domain.reject(pairing, user)
    await session.commit()
    return pairing


async def cancel(session: AsyncSession, user: User, pairing_id: UUID) -> None:
    pairing = await own_pairing(session, user, pairing_id)
    domain.cancel(pairing, user)
    await session.commit()

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.deps import CurrentUser, DbSession
from max_assist.modules.assist import service as assist_service
from max_assist.modules.identity.models import User
from max_assist.modules.notifications import service as notifications
from max_assist.modules.trust import domain, service
from max_assist.modules.trust.models import Pairing, TrustedHelper

router = APIRouter(tags=["trust"])


class PersonOut(BaseModel):
    id: UUID
    display_name: str
    photo_url: str | None


class OwnerOut(BaseModel):
    display_name: str
    photo_url: str | None


class ClaimerOut(BaseModel):
    display_name: str
    photo_url: str | None
    max_username: str | None


class TrustedHelperOut(BaseModel):
    id: UUID
    helper: PersonOut
    alias: str | None
    verification_method: str
    created_at: datetime
    last_helped_at: datetime | None


class HelpingForOut(BaseModel):
    id: UUID
    owner: OwnerOut
    active_assist_session_id: UUID | None
    created_at: datetime


class RenameIn(BaseModel):
    alias: str | None = None


class PairingIn(BaseModel):
    method: Literal["qr", "link"] = "qr"


class PairingOut(BaseModel):
    id: UUID
    method: str
    status: str
    token: str
    qr_payload: str
    deep_link: str
    expires_at: datetime


class PairingStateOut(BaseModel):
    id: UUID
    status: str
    expires_at: datetime
    claimed_by: ClaimerOut | None


class ConfirmIn(BaseModel):
    alias: str | None = None


class PairingPreviewOut(BaseModel):
    status: Literal["valid", "expired", "used", "self", "already_trusted"]
    owner: OwnerOut


class ClaimOut(BaseModel):
    pairing_id: UUID
    status: str


def pairing_link(token: str) -> str:
    return notifications.app_link(f"pr_{token}")


async def helper_view(db: AsyncSession, trusted: TrustedHelper) -> TrustedHelperOut:
    helper = await db.get(User, trusted.helper_id)
    return TrustedHelperOut(
        id=trusted.id,
        helper=PersonOut(id=helper.id, display_name=helper.display_name, photo_url=helper.photo_url),
        alias=trusted.alias,
        verification_method=trusted.verification_method,
        created_at=trusted.created_at,
        last_helped_at=await assist_service.last_help(db, trusted.owner_id, trusted.helper_id),
    )


async def pairing_state(db: AsyncSession, pairing: Pairing) -> PairingStateOut:
    claimer = await db.get(User, pairing.claimed_by) if pairing.claimed_by else None
    return PairingStateOut(
        id=pairing.id,
        status=domain.status_of(pairing),
        expires_at=pairing.expires_at,
        claimed_by=ClaimerOut(
            display_name=claimer.display_name,
            photo_url=claimer.photo_url,
            max_username=claimer.username,
        )
        if claimer
        else None,
    )


@router.get("/trusted-helpers", response_model=list[TrustedHelperOut])
async def my_helpers(user: CurrentUser, db: DbSession) -> list[TrustedHelperOut]:
    return [await helper_view(db, item) for item in await service.my_helpers(db, user)]


@router.get("/trusted-helpers/helping-for", response_model=list[HelpingForOut])
async def helping_for(user: CurrentUser, db: DbSession) -> list[HelpingForOut]:
    result = []
    for item in await service.helping_for(db, user):
        owner = await db.get(User, item.owner_id)
        result.append(
            HelpingForOut(
                id=item.id,
                owner=OwnerOut(display_name=owner.display_name, photo_url=owner.photo_url),
                active_assist_session_id=await assist_service.live_session_with(db, item.owner_id, user.id),
                created_at=item.created_at,
            )
        )
    return result


@router.patch("/trusted-helpers/{trusted_id}", response_model=TrustedHelperOut)
async def rename(trusted_id: UUID, payload: RenameIn, user: CurrentUser, db: DbSession) -> TrustedHelperOut:
    trusted = await service.rename(db, user, trusted_id, payload.alias)
    return await helper_view(db, trusted)


@router.delete("/trusted-helpers/{trusted_id}", status_code=204)
async def revoke(trusted_id: UUID, user: CurrentUser, db: DbSession) -> Response:
    await service.revoke(db, user, trusted_id)
    return Response(status_code=204)


@router.post("/pairings", response_model=PairingOut, status_code=201)
async def start_pairing(payload: PairingIn, user: CurrentUser, db: DbSession) -> PairingOut:
    pairing, token = await service.start_pairing(db, user, payload.method)
    link = pairing_link(token)
    return PairingOut(
        id=pairing.id,
        method=pairing.method,
        status=pairing.status,
        token=token,
        qr_payload=link,
        deep_link=link,
        expires_at=pairing.expires_at,
    )


@router.get("/pairings/{pairing_id}", response_model=PairingStateOut)
async def get_pairing(pairing_id: UUID, user: CurrentUser, db: DbSession) -> PairingStateOut:
    return await pairing_state(db, await service.own_pairing(db, user, pairing_id))


@router.post("/pairings/{pairing_id}/confirm", response_model=TrustedHelperOut, status_code=201)
async def confirm(pairing_id: UUID, payload: ConfirmIn, user: CurrentUser, db: DbSession) -> TrustedHelperOut:
    trusted = await service.confirm(db, user, pairing_id, payload.alias)
    return await helper_view(db, trusted)


@router.post("/pairings/{pairing_id}/reject", response_model=PairingStateOut)
async def reject(pairing_id: UUID, user: CurrentUser, db: DbSession) -> PairingStateOut:
    return await pairing_state(db, await service.reject(db, user, pairing_id))


@router.delete("/pairings/{pairing_id}", status_code=204)
async def cancel(pairing_id: UUID, user: CurrentUser, db: DbSession) -> Response:
    await service.cancel(db, user, pairing_id)
    return Response(status_code=204)


@router.get("/pairing-tokens/{token}", response_model=PairingPreviewOut)
async def preview(token: str, user: CurrentUser, db: DbSession) -> PairingPreviewOut:
    pairing, status = await service.preview(db, user, token)
    owner = await db.get(User, pairing.owner_id)
    return PairingPreviewOut(
        status=status, owner=OwnerOut(display_name=owner.display_name, photo_url=owner.photo_url)
    )


@router.post("/pairing-tokens/{token}/claim", response_model=ClaimOut)
async def claim(token: str, user: CurrentUser, db: DbSession) -> ClaimOut:
    pairing = await service.claim(db, user, token)
    return ClaimOut(pairing_id=pairing.id, status=pairing.status)

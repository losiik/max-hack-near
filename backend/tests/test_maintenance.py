import asyncio
import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, update

from max_assist import maintenance, tasks
from max_assist.config import settings
from max_assist.db import session_factory
from max_assist.modules.applications.models import ServiceSession, ServiceSessionInbox
from max_assist.modules.assist.models import AssistInvite, AssistParticipant, AssistSession, HelpCallback
from max_assist.utils import now
from tests.helpers import login, reach_confirmation, start_session
from tests.test_application_flow_details import submit
from tests.test_assist_api import invite, joined_helper, owner_with_assist


async def age(model, row_id, **columns):
    async with session_factory() as db:
        await db.execute(update(model).where(model.id == UUID(str(row_id))).values(**columns))
        await db.commit()


async def exists(model, row_id) -> bool:
    async with session_factory() as db:
        return await db.get(model, UUID(str(row_id))) is not None


async def say_busy(client, owner_headers, assist_id, user_key):
    helper_headers = await login(client, user_key)
    token = (await invite(client, owner_headers, assist_id))["token"]
    declined = await client.post(f"/api/v1/assist-invites/{token}/decline", headers=helper_headers)
    return declined.json()["help_callback_id"]


async def run_cleanup() -> dict[str, int]:
    async with session_factory() as db:
        return await maintenance.cleanup(db)


async def test_abandoned_drafts_are_removed_but_meetings_stay(client):
    _, old_application, body = await owner_with_assist(client)
    anna = await login(client, "anna")
    fresh_application = await start_session(client, anna)
    await age(ServiceSession, old_application, updated_at=now() - timedelta(days=31))

    removed = await run_cleanup()

    assert removed["drafts"] >= 1
    assert not await exists(ServiceSession, old_application)
    assert await exists(ServiceSession, fresh_application)
    async with session_factory() as db:
        meeting = await db.get(AssistSession, UUID(body["id"]))
    assert meeting.service_session_id is None


async def test_submitted_applications_are_kept_for_the_retention_period(client):
    oleg = await login(client, "oleg")
    recent = await start_session(client, oleg)
    await submit(client, oleg, recent)
    anna = await login(client, "anna")
    old = await start_session(client, anna)
    await submit(client, anna, old)

    await age(ServiceSession, recent, submitted_at=now() - timedelta(days=10))
    await age(ServiceSession, old, submitted_at=now() - timedelta(days=91))
    await run_cleanup()

    assert await exists(ServiceSession, recent)
    assert not await exists(ServiceSession, old)


async def test_sms_codes_are_removed_after_a_day(client):
    sergey = await login(client, "sergey")
    application = await start_session(client, sergey)
    await reach_confirmation(client, sergey, application)
    await client.post(f"/api/v1/service-sessions/{application}/confirmation-code", headers=sergey)

    async with session_factory() as db:
        message = await db.scalar(
            select(ServiceSessionInbox.id).where(ServiceSessionInbox.service_session_id == UUID(application))
        )
    await age(ServiceSessionInbox, message, created_at=now() - timedelta(hours=25))
    await run_cleanup()

    assert not await exists(ServiceSessionInbox, message)
    assert await exists(ServiceSession, application)


async def test_old_invites_are_removed_and_meetings_are_kept(client):
    headers, application, body = await owner_with_assist(client)
    _, participant_id = await joined_helper(client, headers, body["id"])

    async with session_factory() as db:
        invite = await db.scalar(
            select(AssistInvite.id).where(AssistInvite.assist_session_id == UUID(body["id"]))
        )
    await age(AssistInvite, invite, created_at=now() - timedelta(days=8))
    await run_cleanup()

    async with session_factory() as db:
        participant = await db.get(AssistParticipant, UUID(participant_id))
    assert not await exists(AssistInvite, invite)
    assert participant is not None
    assert participant.invite_id is None

    await client.post(f"/api/v1/assist-sessions/{body['id']}/end", headers=headers)
    await age(AssistSession, body["id"], ended_at=now() - timedelta(days=400))
    await run_cleanup()

    assert await exists(AssistSession, body["id"])
    assert await exists(ServiceSession, application)


async def test_old_and_closed_promises_to_help_are_removed(client):
    headers, _, body = await owner_with_assist(client)
    open_id, closed_id, forgotten_id = [
        await say_busy(client, headers, body["id"], user_key) for user_key in ("sergey", "oleg", "anna")
    ]
    await client.delete(f"/api/v1/help-callbacks/{closed_id}", headers=headers)
    await age(HelpCallback, closed_id, closed_at=now() - timedelta(days=8))
    await age(HelpCallback, forgotten_id, expires_at=now() - timedelta(days=8))

    removed = await run_cleanup()

    assert removed["help_callbacks"] == 2
    assert await exists(HelpCallback, open_id)


async def test_live_data_is_not_touched(client):
    headers, application, body = await owner_with_assist(client)

    await run_cleanup()

    assert await exists(ServiceSession, application)
    assert await exists(AssistSession, body["id"])


async def test_cleanup_reports_removed_rows_and_a_too_big_database(client, monkeypatch, caplog):
    _, application, _ = await owner_with_assist(client)
    await age(ServiceSession, application, updated_at=now() - timedelta(days=31))
    monkeypatch.setattr(settings, "db_size_warning_mb", 0)

    with caplog.at_level(logging.INFO, logger="max_assist.maintenance"):
        await maintenance.run_once()

    assert "cleanup removed" in caplog.text
    assert "database takes" in caplog.text


async def test_failed_cleanup_does_not_stop_the_schedule(monkeypatch, caplog):
    attempts = []
    enough = asyncio.Event()

    async def broken():
        attempts.append(True)
        if len(attempts) >= 3:
            enough.set()
        raise RuntimeError("database is down")

    monkeypatch.setattr(maintenance, "run_once", broken)
    monkeypatch.setattr(settings, "cleanup_interval_minutes", 0)

    with caplog.at_level(logging.ERROR, logger="max_assist.maintenance"):
        schedule = asyncio.create_task(maintenance.run_forever())
        await asyncio.wait_for(enough.wait(), timeout=5)
        schedule.cancel()
        await asyncio.gather(schedule, return_exceptions=True)
        await tasks.wait_background()

    assert len(attempts) >= 3
    assert "cleanup failed" in caplog.text

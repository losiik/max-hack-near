import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from starlette.testclient import TestClient

import max_assist.models  # noqa: F401
from max_assist import maintenance, tasks
from max_assist.config import settings
from max_assist.db import Base, engine, session_factory
from max_assist.main import app
from max_assist.modules.assist import expiry


async def test_health_reports_database_and_its_size(client):
    response = await client.get("/health")

    body = response.json()
    assert response.status_code == 200
    assert (body["status"], body["db"]) == ("ok", "ok")
    assert body["db_size_mb"] > 0


async def test_health_warns_when_database_is_too_big(client, monkeypatch):
    monkeypatch.setattr(settings, "db_size_warning_mb", 0)

    response = await client.get("/health")

    assert response.json()["status"] == "degraded"


def test_all_tables_are_registered_for_migrations():
    assert set(Base.metadata.tables) == {
        "users",
        "services",
        "service_sessions",
        "service_session_inbox",
        "assist_sessions",
        "help_callbacks",
        "assist_participants",
        "assist_invites",
        "session_events",
    }


async def test_database_sessions_have_safety_timeouts(client):
    async with session_factory() as db:
        name = await db.scalar(text("show application_name"))
        statement = await db.scalar(text("show statement_timeout"))
        idle_in_transaction = await db.scalar(text("show idle_in_transaction_session_timeout"))
        idle = await db.scalar(text("show idle_session_timeout"))

    assert name == "ryadom-api"
    assert (statement, idle_in_transaction, idle) == ("30s", "1min", "10min")


async def test_transaction_left_open_is_ended_by_the_server(client):
    db = session_factory()
    try:
        await db.execute(text("set idle_in_transaction_session_timeout = '300ms'"))
        await asyncio.sleep(0.6)
        with pytest.raises(DBAPIError):
            await db.execute(text("select 1"))
    finally:
        await db.close()

    async with session_factory() as fresh:
        assert await fresh.scalar(text("select 1")) == 1


def test_shutdown_waits_for_background_work():
    finished = []

    async def slow_work():
        await asyncio.sleep(0.2)
        finished.append(True)

    async def schedule():
        tasks.run_in_background(slow_work())

    with TestClient(app) as client:
        client.portal.call(schedule)

    assert finished == [True]


def test_cleanup_runs_on_startup_and_stops_with_the_app(monkeypatch):
    runs = []
    original = maintenance.run_once

    async def counted():
        runs.append(True)
        await original()

    monkeypatch.setattr(settings, "cleanup_enabled", True)
    monkeypatch.setattr(maintenance, "run_once", counted)

    with TestClient(app) as client:
        client.portal.call(asyncio.sleep, 0.5)

    assert runs == [True]
    assert engine.pool.checkedout() == 0


def test_expiry_runs_on_startup_and_stops_with_the_app(monkeypatch):
    runs = []

    async def counted():
        runs.append(True)

    monkeypatch.setattr(settings, "expiry_enabled", True)
    monkeypatch.setattr(expiry, "run_once", counted)

    with TestClient(app) as client:
        client.portal.call(asyncio.sleep, 0.3)

    assert runs == [True]

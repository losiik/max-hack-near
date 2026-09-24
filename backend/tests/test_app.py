import max_assist.models  # noqa: F401
from max_assist.db import Base


async def test_health_reports_database(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_all_tables_are_registered_for_migrations():
    assert set(Base.metadata.tables) == {
        "users",
        "services",
        "service_sessions",
        "service_session_inbox",
    }

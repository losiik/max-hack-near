from uuid import uuid4

import pytest

from max_assist.config import settings
from max_assist.modules.notifications import service as notifications
from tests.test_help_callbacks import busy_helper


@pytest.fixture(autouse=True)
def empty_outbox():
    notifications.outbox.clear()
    yield
    notifications.outbox.clear()


async def outbox(client, headers):
    response = await client.get("/api/v1/dev/outbox", headers=headers)
    assert response.status_code == 200
    return response.json()


async def test_busy_helper_is_offered_a_button_to_come_back(client):
    headers, helper_headers, _, _, callback_id = await busy_helper(client)

    [to_owner] = await outbox(client, headers)
    [to_helper] = await outbox(client, helper_headers)

    assert to_owner["text"].startswith("Сергей К. сейчас не может помочь")
    assert "Людмила П." in to_helper["text"]
    assert to_helper["buttons"] == [{"text": "Теперь могу помочь", "start_param": f"ar_{callback_id}"}]


async def test_owner_is_told_when_helper_can_help_and_helper_gets_a_new_invite(client):
    headers, helper_headers, _, _, callback_id = await busy_helper(client)

    await client.post(f"/api/v1/help-callbacks/{callback_id}/ready", headers=helper_headers)
    ready = (await outbox(client, headers))[0]
    called = (await client.post(f"/api/v1/help-callbacks/{callback_id}/call", headers=headers)).json()
    invite = (await outbox(client, helper_headers))[0]

    token = called["invite"]["token"]
    assert ready["text"] == "Сергей К. может помочь с услугой «Компенсация расходов на оплату ЖКУ»"
    assert invite["text"] == "Людмила П. просит помочь с услугой «Компенсация расходов на оплату ЖКУ»"
    assert [button["start_param"] for button in invite["buttons"]] == [f"as_{token}", f"ad_{token}"]


async def test_outbox_keeps_only_the_latest_messages():
    user_id = uuid4()
    for number in range(notifications.OUTBOX_SIZE + 5):
        notifications.send(user_id, f"сообщение {number}", [])

    kept = notifications.messages_for(user_id)

    assert len(kept) == notifications.OUTBOX_SIZE
    assert kept[0].text == f"сообщение {notifications.OUTBOX_SIZE + 4}"
    assert notifications.messages_for(uuid4()) == []


async def test_outbox_is_closed_outside_dev(client, monkeypatch):
    headers, _, _, _, _ = await busy_helper(client)
    monkeypatch.setattr(settings, "app_env", "prod")

    response = await client.get("/api/v1/dev/outbox", headers=headers)

    assert response.status_code == 403

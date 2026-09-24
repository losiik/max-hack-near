from uuid import uuid4

from max_assist.modules.assist.realtime import Hub, Viewer


class FakeSocket:
    def __init__(self, broken: bool = False) -> None:
        self.broken = broken
        self.sent: list[dict] = []
        self.closed_with: int | None = None

    async def send_json(self, message: dict) -> None:
        if self.broken:
            raise RuntimeError("socket is closed")
        self.sent.append(message)

    async def close(self, code: int) -> None:
        if self.broken:
            raise RuntimeError("socket is closed")
        self.closed_with = code


def viewer(participant_id, status="active", role="invited_helper"):
    return Viewer(participant_id=participant_id, role=role, status=status, display_name="Сергей К.")


async def test_messages_before_greeting_wait_and_stale_ones_are_dropped():
    hub = Hub()
    session_id, participant_id = uuid4(), uuid4()
    socket = FakeSocket()
    connection, _ = hub.connect(session_id, viewer(participant_id), socket)

    await hub.send(session_id, [participant_id], {"event": "already_in_snapshot", "seq": 3})
    await hub.send(session_id, [participant_id], {"event": "newer_than_snapshot", "seq": 5})
    await hub.send(session_id, [participant_id], {"event": "presence", "seq": None})
    assert socket.sent == []

    await connection.open({"event": "session.snapshot", "seq": None}, last_seq=4)
    await hub.send(session_id, [participant_id], {"event": "after", "seq": 6})

    assert [message["event"] for message in socket.sent] == [
        "session.snapshot",
        "newer_than_snapshot",
        "presence",
        "after",
    ]


async def test_participant_is_online_while_any_connection_is_open():
    hub = Hub()
    session_id, participant_id = uuid4(), uuid4()

    first, came_online = hub.connect(session_id, viewer(participant_id), FakeSocket())
    second, came_online_again = hub.connect(session_id, viewer(participant_id), FakeSocket())

    assert (came_online, came_online_again) == (True, False)
    assert hub.online(session_id) == {participant_id}
    assert hub.disconnect(session_id, participant_id, first) is False
    assert hub.disconnect(session_id, participant_id, second) is True
    assert hub.online(session_id) == set()
    assert hub.sessions == {}


async def test_disconnecting_twice_does_not_report_leaving_twice():
    hub = Hub()
    session_id, participant_id = uuid4(), uuid4()
    connection, _ = hub.connect(session_id, viewer(participant_id), FakeSocket())

    assert hub.disconnect(session_id, participant_id, connection) is True
    assert hub.disconnect(session_id, participant_id, connection) is False
    assert hub.online(session_id) == set()


async def test_only_approved_participants_are_counted_as_active():
    hub = Hub()
    session_id, owner_id, helper_id = uuid4(), uuid4(), uuid4()
    hub.connect(session_id, viewer(owner_id, role="owner"), FakeSocket())
    hub.connect(session_id, viewer(helper_id, status="pending"), FakeSocket())

    assert hub.active_participants(session_id) == [owner_id]

    hub.update_status(session_id, helper_id, "active")

    assert sorted(hub.active_participants(session_id)) == sorted([owner_id, helper_id])
    assert hub.active_participants(session_id, exclude=owner_id) == [helper_id]


async def test_broken_socket_does_not_stop_delivery_to_others():
    hub = Hub()
    session_id = uuid4()
    broken_id, healthy_id = uuid4(), uuid4()
    broken, _ = hub.connect(session_id, viewer(broken_id), FakeSocket(broken=True))
    healthy_socket = FakeSocket()
    healthy, _ = hub.connect(session_id, viewer(healthy_id), healthy_socket)
    broken.ready = healthy.ready = True

    await hub.send(session_id, [broken_id, healthy_id], {"event": "ping", "seq": None})
    await hub.close(session_id, [broken_id, healthy_id], 4009)

    assert healthy_socket.sent == [{"event": "ping", "seq": None}]
    assert healthy_socket.closed_with == 4009


async def test_sending_to_unknown_session_is_harmless():
    hub = Hub()

    await hub.send(uuid4(), [uuid4()], {"event": "nothing", "seq": None})
    await hub.close(uuid4(), [uuid4()], 1000)

    assert hub.sessions == {}

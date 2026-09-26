from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass
class Viewer:
    participant_id: UUID
    role: str
    status: str
    display_name: str


class Connection:
    def __init__(self, websocket: Any, viewer: Viewer) -> None:
        self.websocket = websocket
        self.viewer = viewer
        self.ready = False
        self.backlog: list[dict[str, Any]] = []

    async def send(self, message: dict[str, Any]) -> None:
        if not self.ready:
            self.backlog.append(message)
            return
        await self.websocket.send_json(message)

    async def open(self, greeting: dict[str, Any], last_seq: int) -> None:
        await self.websocket.send_json(greeting)
        while self.backlog:
            message = self.backlog.pop(0)
            if message["seq"] is None or message["seq"] > last_seq:
                await self.websocket.send_json(message)
        self.ready = True


class Hub:
    def __init__(self) -> None:
        self.sessions: dict[UUID, dict[UUID, list[Connection]]] = {}
        self.select_views: dict[UUID, dict[str, Any] | None] = {}

    def set_select_view(self, assist_id: UUID, view: dict[str, Any] | None) -> None:
        if view is None:
            self.select_views.pop(assist_id, None)
        else:
            self.select_views[assist_id] = view

    def get_select_view(self, assist_id: UUID) -> dict[str, Any] | None:
        return self.select_views.get(assist_id)

    def connect(self, assist_id: UUID, viewer: Viewer, websocket: Any) -> tuple[Connection, bool]:
        connections = self.sessions.setdefault(assist_id, {}).setdefault(viewer.participant_id, [])
        connection = Connection(websocket, viewer)
        connections.append(connection)
        return connection, len(connections) == 1

    def disconnect(self, assist_id: UUID, participant_id: UUID, connection: Connection) -> bool:
        participants = self.sessions.get(assist_id, {})
        connections = participants.get(participant_id, [])
        if connection not in connections:
            return False

        connections.remove(connection)
        if connections:
            return False

        participants.pop(participant_id, None)
        if not participants:
            self.sessions.pop(assist_id, None)
        return True

    def online(self, assist_id: UUID) -> set[UUID]:
        return set(self.sessions.get(assist_id, {}))

    def update_status(self, assist_id: UUID, participant_id: UUID, status: str) -> None:
        for connection in self.sessions.get(assist_id, {}).get(participant_id, []):
            connection.viewer.status = status

    def active_participants(self, assist_id: UUID, exclude: UUID | None = None) -> list[UUID]:
        found = []
        for participant_id, connections in self.sessions.get(assist_id, {}).items():
            if participant_id == exclude:
                continue
            if any(connection.viewer.status == "active" for connection in connections):
                found.append(participant_id)
        return found

    def connections(self, assist_id: UUID, participant_ids: list[UUID]) -> list[Connection]:
        participants = self.sessions.get(assist_id, {})
        found: list[Connection] = []
        for participant_id in participant_ids:
            found.extend(participants.get(participant_id, []))
        return found

    async def send(self, assist_id: UUID, participant_ids: list[UUID], message: dict[str, Any]) -> None:
        for connection in self.connections(assist_id, participant_ids):
            try:
                await connection.send(message)
            except Exception:
                continue

    async def close(self, assist_id: UUID, participant_ids: list[UUID], code: int) -> None:
        for connection in self.connections(assist_id, participant_ids):
            try:
                await connection.websocket.close(code)
            except Exception:
                continue


hub = Hub()

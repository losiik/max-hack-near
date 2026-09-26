import json
import logging
from collections.abc import AsyncIterator
from itertools import count
from typing import Any

import httpx
import websockets

logger = logging.getLogger("digital_employee")


class Backend:
    # агент для backend — обычный участник встречи со своим токеном
    def __init__(self, base_url: str, assist_id: str, token: str, transport: Any = None) -> None:
        self.assist_id = assist_id
        self.token = token
        self.ws_url = base_url.replace("http", "ws", 1) + f"/ws/assist/{assist_id}?token={token}"
        self.http = httpx.AsyncClient(
            base_url=base_url + "/api/v1",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
            transport=transport,
        )
        self.ws: Any = None
        self.request_ids = count(1)

    async def connect(self) -> dict[str, Any]:
        self.ws = await websockets.connect(self.ws_url, open_timeout=10)
        greeting = json.loads(await self.ws.recv())
        if greeting["event"] != "session.snapshot":
            raise RuntimeError(f"expected a snapshot, got {greeting['event']}")
        return greeting["payload"]

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        try:
            async for raw in self.ws:
                yield json.loads(raw)
        except websockets.ConnectionClosed:
            pass

    async def command(self, name: str, payload: dict[str, Any]) -> None:
        message = {"command": name, "request_id": f"agent-{next(self.request_ids)}", "payload": payload}
        await self.ws.send(json.dumps(message, ensure_ascii=False))

    async def highlight(self, element_id: str, label: str | None = None) -> None:
        await self.command("annotation.highlight", {"element_id": element_id, "label": label})

    async def point(self, element_id: str) -> None:
        await self.command(
            "annotation.pointer", {"element_id": element_id, "rel_x": 0.5, "rel_y": 0.5, "visible": True}
        )

    async def call_operator(self, summary: str) -> bool:
        response = await self.http.post(
            f"/assist-sessions/{self.assist_id}/operator-requests",
            json={"topic": "dont_understand", "summary": summary},
        )
        # сотрудник уже вызван — это тоже успех для человека
        return response.status_code in (201, 409)

    async def record_turn(self, turn: dict[str, Any]) -> None:
        try:
            response = await self.http.post("/ai-turns", json=turn)
            if response.status_code != 201:
                logger.warning("turn was not saved: %s %s", response.status_code, response.text[:200])
        except httpx.HTTPError:
            logger.exception("turn was not saved")

    async def leave(self) -> None:
        try:
            await self.http.delete(f"/assist-sessions/{self.assist_id}/ai-agent")
        except httpx.HTTPError:
            logger.exception("could not leave the meeting")

    async def close(self) -> None:
        if self.ws is not None:
            await self.ws.close()
        await self.http.aclose()

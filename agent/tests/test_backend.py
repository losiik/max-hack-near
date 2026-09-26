import json

import httpx

from digital_employee.backend import Backend


class FakeApi:
    def __init__(self, status=201):
        self.requests = []
        self.status = status

    def __call__(self, request):
        self.requests.append(request)
        return httpx.Response(self.status, json={"id": "x"})


def backend(api):
    return Backend("http://api:8000", "assist-1", "agent-token", transport=httpx.MockTransport(api))


def test_socket_address_carries_the_agent_token():
    agent = Backend("https://example.ru", "assist-1", "agent-token")

    assert agent.ws_url == "wss://example.ru/ws/assist/assist-1?token=agent-token"


async def test_agent_calls_an_operator_with_a_summary():
    api = FakeApi()
    summary = "Не понимает, какой доход указать"

    called = await backend(api).call_operator(summary)
    request = api.requests[0]

    assert called
    assert request.url.path == "/api/v1/assist-sessions/assist-1/operator-requests"
    assert request.headers["authorization"] == "Bearer agent-token"
    assert json.loads(request.content) == {"topic": "dont_understand", "summary": summary}


async def test_operator_already_called_is_fine():
    assert await backend(FakeApi(409)).call_operator("…")
    assert not await backend(FakeApi(403)).call_operator("…")


async def test_turn_is_recorded_and_failure_does_not_break_the_agent():
    api = FakeApi()
    turn = {"trigger": "question", "reply_text": "Выберите первый вариант."}

    await backend(api).record_turn(turn)
    await backend(FakeApi(500)).record_turn(turn)

    assert api.requests[0].url.path == "/api/v1/ai-turns"
    assert json.loads(api.requests[0].content) == turn


async def test_agent_leaves_the_meeting():
    api = FakeApi(204)

    await backend(api).leave()

    assert (api.requests[0].method, api.requests[0].url.path) == (
        "DELETE",
        "/api/v1/assist-sessions/assist-1/ai-agent",
    )

import gc
import json
import re
from uuid import uuid4

import pytest
from starlette.websockets import WebSocketDisconnect

from tests.helpers import STEP_VALUES, settle

SECRET_ADDRESS = "Тайная улица, дом 7731"


def login(api, user_key):
    token = api.post("/api/v1/auth/dev-login", json={"user_key": user_key}).json()["access_token"]
    api.post("/api/v1/me/recording-consent", headers=auth(token))
    return token


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def socket_url(assist_id, token):
    return f"/ws/assist/{assist_id}?token={token}"


def owner_with_assist(api):
    owner = login(api, "ludmila")
    api.post("/api/v1/dev/reset", headers=auth(owner))
    application = api.post(
        "/api/v1/service-sessions",
        json={"service_code": "housing_compensation"},
        headers=auth(owner),
    ).json()
    assist = api.post(
        "/api/v1/assist-sessions",
        json={"service_session_id": application["id"]},
        headers=auth(owner),
    ).json()
    return owner, assist


def request_to_join(api, owner, assist_id, user_key="sergey"):
    helper = login(api, user_key)
    token = api.post(
        f"/api/v1/assist-sessions/{assist_id}/invites",
        json={"kind": "link"},
        headers=auth(owner),
    ).json()["token"]
    accepted = api.post(f"/api/v1/assist-invites/{token}/accept", headers=auth(helper)).json()
    return helper, accepted["participant_id"]


def active_helper(api, owner, assist_id, user_key="sergey"):
    helper, participant_id = request_to_join(api, owner, assist_id, user_key)
    api.post(
        f"/api/v1/assist-sessions/{assist_id}/participants/{participant_id}/approve",
        headers=auth(owner),
    )
    return helper, participant_id


def reach_confirmation(api, owner, application_id):
    for values in STEP_VALUES.values():
        api.patch(
            f"/api/v1/service-sessions/{application_id}/fields",
            json={"values": values},
            headers=auth(owner),
        )
        moved = api.post(
            f"/api/v1/service-sessions/{application_id}/navigation",
            json={"action": "next"},
            headers=auth(owner),
        )
        assert moved.status_code == 200, moved.text


def elements_of(message):
    return {item["id"]: item for item in message["payload"]["current_step"]["elements"]}


def closed_code(ws):
    with pytest.raises(WebSocketDisconnect) as closed:
        ws.receive_json()
    return closed.value.code


def test_broken_token_is_refused(api):
    _, assist = owner_with_assist(api)

    with api.websocket_connect(socket_url(assist["id"], "broken")) as ws:
        assert closed_code(ws) == 4001


def test_stranger_and_unknown_session_are_refused(api):
    _, assist = owner_with_assist(api)
    stranger = login(api, "oleg")

    with api.websocket_connect(socket_url(assist["id"], stranger)) as ws:
        assert closed_code(ws) == 4003
    with api.websocket_connect(socket_url(uuid4(), stranger)) as ws:
        assert closed_code(ws) == 4004


def test_owner_gets_snapshot_on_connect(api):
    owner, assist = owner_with_assist(api)

    with api.websocket_connect(socket_url(assist["id"], owner)) as ws:
        snapshot = ws.receive_json()

    session = snapshot["payload"]["session"]
    assert snapshot["event"] == "session.snapshot"
    assert snapshot["seq"] is None
    assert snapshot["session_id"] == assist["id"]
    assert snapshot["payload"]["last_seq"] == 0
    assert session["me"]["role"] == "owner"
    assert session["ws_url"] == f"/ws/assist/{assist['id']}"
    assert [item["online"] for item in session["participants"]] == [True]


def test_rest_view_shows_who_is_online(api):
    owner, assist = owner_with_assist(api)

    with api.websocket_connect(socket_url(assist["id"], owner)) as ws:
        ws.receive_json()
        inside = api.get(f"/api/v1/assist-sessions/{assist['id']}", headers=auth(owner)).json()
    outside = api.get(f"/api/v1/assist-sessions/{assist['id']}", headers=auth(owner)).json()

    assert inside["participants"][0]["online"] is True
    assert outside["participants"][0]["online"] is False


def test_join_request_and_approval_reach_both_sides(api):
    owner, assist = owner_with_assist(api)

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        helper, participant_id = request_to_join(api, owner, assist["id"])

        request = owner_ws.receive_json()
        assert request["event"] == "participant.join_requested"
        assert request["seq"] == 1
        assert request["actor"]["participant_id"] == participant_id
        assert request["payload"]["participant"]["display_name"] == "Сергей К."

        with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
            pending = helper_ws.receive_json()
            assert pending["event"] == "session.pending"
            assert pending["payload"]["owner"]["display_name"] == "Людмила П."

            api.post(
                f"/api/v1/assist-sessions/{assist['id']}/participants/{participant_id}/approve",
                headers=auth(owner),
            )

            joined = owner_ws.receive_json()
            activated = owner_ws.receive_json()
            status = helper_ws.receive_json()
            snapshot = helper_ws.receive_json()

            assert (joined["event"], joined["seq"]) == ("participant.joined", 2)
            assert joined["payload"]["participant"]["online"] is True
            assert (activated["event"], activated["seq"]) == ("session.activated", 3)
            assert status["payload"] == {"participant_id": participant_id, "status": "active"}
            assert snapshot["event"] == "session.snapshot"
            assert snapshot["payload"]["last_seq"] == 4
            assert snapshot["payload"]["session"]["me"]["role"] == "invited_helper"

        offline = owner_ws.receive_json()
        assert offline["event"] == "presence.changed"
        assert offline["payload"] == {"participant_id": participant_id, "online": False}

        with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
            helper_ws.receive_json()
            online = owner_ws.receive_json()
            assert online["payload"] == {"participant_id": participant_id, "online": True}


def test_rejected_helper_is_told_and_disconnected(api):
    owner, assist = owner_with_assist(api)
    helper, participant_id = request_to_join(api, owner, assist["id"], "oleg")

    with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
        helper_ws.receive_json()
        api.post(
            f"/api/v1/assist-sessions/{assist['id']}/participants/{participant_id}/reject",
            headers=auth(owner),
        )

        status = helper_ws.receive_json()
        assert status["payload"]["status"] == "rejected"
        assert closed_code(helper_ws) == 4003

    with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
        assert closed_code(helper_ws) == 4003


def test_leaving_helper_is_announced_and_disconnected(api):
    owner, assist = owner_with_assist(api)
    helper, participant_id = active_helper(api, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
            helper_ws.receive_json()
            assert owner_ws.receive_json()["payload"]["online"] is True

            api.post(f"/api/v1/assist-sessions/{assist['id']}/leave", headers=auth(helper))

            left = owner_ws.receive_json()
            assert left["event"] == "participant.left"
            assert left["payload"] == {"participant_id": participant_id, "reason": "left"}
            assert left["actor"]["participant_id"] == participant_id
            assert closed_code(helper_ws) == 1000


def test_removed_helper_is_told_and_disconnected(api):
    owner, assist = owner_with_assist(api)
    helper, participant_id = active_helper(api, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
            helper_ws.receive_json()
            owner_ws.receive_json()

            api.delete(
                f"/api/v1/assist-sessions/{assist['id']}/participants/{participant_id}",
                headers=auth(owner),
            )

            left = owner_ws.receive_json()
            status = helper_ws.receive_json()
            assert left["payload"] == {"participant_id": participant_id, "reason": "removed"}
            assert status["payload"]["status"] == "removed"
            assert closed_code(helper_ws) == 4003


def test_end_reaches_everyone_and_closes_the_channel(api):
    owner, assist = owner_with_assist(api)
    helper, _ = active_helper(api, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
            helper_ws.receive_json()
            owner_ws.receive_json()

            api.post(f"/api/v1/assist-sessions/{assist['id']}/end", headers=auth(owner))

            for ws in (owner_ws, helper_ws):
                ended = ws.receive_json()
                assert ended["event"] == "session.ended"
                assert ended["payload"]["reason"] == "owner_ended"
                assert ended["payload"]["summary_url"].endswith(f"/assist-sessions/{assist['id']}/summary")
                assert closed_code(ws) == 4009

    with api.websocket_connect(socket_url(assist["id"], owner)) as ws:
        assert closed_code(ws) == 4009


def test_commands_are_answered(api):
    owner, assist = owner_with_assist(api)

    with api.websocket_connect(socket_url(assist["id"], owner)) as ws:
        ws.receive_json()
        ws.send_text("not json")
        bad = ws.receive_json()
        ws.send_json({"command": "presence.ping"})
        ws.send_json({"command": "helper.message", "request_id": "c-1", "payload": {}})
        unknown = ws.receive_json()
        highlight(ws, "benefit_category", request_id="c-2")
        forbidden = ws.receive_json()

    assert bad["event"] == "error"
    assert bad["payload"]["code"] == "bad_message"
    assert unknown["payload"]["request_id"] == "c-1"
    assert unknown["payload"]["code"] == "unknown_command"
    assert forbidden["payload"]["code"] == "forbidden"


def test_second_helper_does_not_restart_the_session(api):
    owner, assist = owner_with_assist(api)
    active_helper(api, owner, assist["id"], "sergey")

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        _, participant_id = request_to_join(api, owner, assist["id"], "anna")
        assert owner_ws.receive_json()["event"] == "participant.join_requested"

        api.post(
            f"/api/v1/assist-sessions/{assist['id']}/participants/{participant_id}/approve",
            headers=auth(owner),
        )
        joined = owner_ws.receive_json()
        api.post(f"/api/v1/assist-sessions/{assist['id']}/end", headers=auth(owner))
        next_event = owner_ws.receive_json()

    assert joined["event"] == "participant.joined"
    assert next_event["event"] == "session.ended"


def test_waiting_person_gets_no_presence_updates(api):
    owner, assist = owner_with_assist(api)
    helper, participant_id = request_to_join(api, owner, assist["id"], "oleg")

    with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
        helper_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
            owner_ws.receive_json()

        api.post(
            f"/api/v1/assist-sessions/{assist['id']}/participants/{participant_id}/reject",
            headers=auth(owner),
        )
        first = helper_ws.receive_json()

    assert first["event"] == "participant.status_changed"


def test_second_tab_does_not_flicker_presence(api):
    owner, assist = owner_with_assist(api)
    helper, participant_id = active_helper(api, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], helper)) as first_tab:
            first_tab.receive_json()
            assert owner_ws.receive_json()["payload"] == {"participant_id": participant_id, "online": True}

            with api.websocket_connect(socket_url(assist["id"], helper)) as second_tab:
                second_tab.receive_json()

            api.post(f"/api/v1/assist-sessions/{assist['id']}/leave", headers=auth(helper))
            next_event = owner_ws.receive_json()

    assert next_event["event"] == "participant.left"


def test_helper_snapshot_shows_form_without_secret_values(api):
    owner, assist = owner_with_assist(api)
    helper, _ = active_helper(api, owner, assist["id"])
    application = f"/api/v1/service-sessions/{assist['service_session_id']}"
    api.patch(
        f"{application}/fields",
        json={"values": {"benefit_category": "pensioner", "benefit_reason": "certificate"}},
        headers=auth(owner),
    )
    api.post(f"{application}/navigation", json={"action": "next"}, headers=auth(owner))
    api.patch(
        f"{application}/fields",
        json={"values": {"region": "spb", "address": "Тайная улица, дом 7731"}},
        headers=auth(owner),
    )

    with api.websocket_connect(socket_url(assist["id"], helper)) as ws:
        payload = ws.receive_json()["payload"]

    elements = {item["id"]: item for item in payload["current_step"]["elements"]}
    assert payload["current_step"]["id"] == "address"
    assert [step["status"] for step in payload["steps"]][:2] == ["completed", "current"]
    assert elements["region"]["view"]["value"] == "spb"
    assert elements["address"]["view"] == {"state": "filled", "value": None, "locked": False}
    assert "Тайная улица" not in json.dumps(payload, ensure_ascii=False)


def test_owner_select_open_and_scroll_are_mirrored_to_helper(api):
    owner, assist = owner_with_assist(api)
    helper, _ = active_helper(api, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
            helper_ws.receive_json()
            owner_ws.receive_json()

            owner_ws.send_json(
                {
                    "command": "owner.select_view",
                    "payload": {
                        "element_id": "benefit_category",
                        "open": True,
                        "scroll_top": 144,
                        "viewport_height": 240,
                    },
                }
            )
            opened = helper_ws.receive_json()
            assert opened["event"] == "form.select_view"
            assert opened["seq"] is None
            assert opened["payload"] == {
                "element_id": "benefit_category",
                "open": True,
                "scroll_top": 144,
                "viewport_height": 240,
            }

            owner_ws.send_json(
                {
                    "command": "owner.select_view",
                    "payload": {"element_id": None, "open": False, "scroll_top": 0, "viewport_height": 0},
                }
            )
            closed = helper_ws.receive_json()
            assert closed["event"] == "form.select_view"
            assert closed["payload"]["open"] is False


def test_form_changes_reach_everyone_in_their_own_projection(api):
    owner, assist = owner_with_assist(api)
    helper, _ = active_helper(api, owner, assist["id"])
    application = f"/api/v1/service-sessions/{assist['service_session_id']}"

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
            start_seq = helper_ws.receive_json()["payload"]["last_seq"]
            owner_ws.receive_json()

            api.post(f"{application}/submit", json={"confirmation_code": "1234"}, headers=auth(owner))
            failed = [owner_ws.receive_json(), helper_ws.receive_json()]

            api.patch(f"{application}/fields", json={"values": STEP_VALUES["category"]}, headers=auth(owner))
            updated = [owner_ws.receive_json(), helper_ws.receive_json()]

            api.post(f"{application}/navigation", json={"action": "next"}, headers=auth(owner))
            moved = [owner_ws.receive_json(), helper_ws.receive_json()]

            api.patch(
                f"{application}/fields",
                json={"values": {"region": "spb", "address": SECRET_ADDRESS}},
                headers=auth(owner),
            )
            secret = [owner_ws.receive_json(), helper_ws.receive_json()]

    rounds = [failed, updated, moved, secret]
    assert [pair[0]["event"] for pair in rounds] == [
        "form.validation_failed",
        "form.field_updated",
        "navigation.step_changed",
        "form.field_updated",
    ]
    for owner_message, helper_message in rounds:
        assert owner_message["event"] == helper_message["event"]
        assert owner_message["seq"] == helper_message["seq"]
    assert [pair[1]["seq"] for pair in rounds] == [start_seq + 1, start_seq + 2, start_seq + 3, start_seq + 4]

    assert failed[1]["payload"]["step_id"] == "category"
    assert {item["element_id"] for item in failed[1]["payload"]["errors"]} == {
        "benefit_category",
        "benefit_reason",
    }
    assert updated[1]["payload"]["element_ids"] == ["benefit_category", "benefit_reason"]
    assert elements_of(updated[1])["benefit_category"]["view"]["value"] == "pensioner"
    assert moved[1]["payload"]["from_step_id"] == "category"
    assert moved[1]["payload"]["current_step"]["id"] == "address"
    assert [step["status"] for step in moved[1]["payload"]["steps"]][:2] == ["completed", "current"]
    assert elements_of(secret[0])["address"]["view"]["value"] == SECRET_ADDRESS
    assert elements_of(secret[1])["address"]["view"] == {"state": "filled", "value": None, "locked": False}
    assert SECRET_ADDRESS not in json.dumps([pair[1] for pair in rounds], ensure_ascii=False)


def test_submitting_the_application_ends_the_assist_session(api):
    owner, assist = owner_with_assist(api)
    helper, _ = active_helper(api, owner, assist["id"])
    application = f"/api/v1/service-sessions/{assist['service_session_id']}"
    reach_confirmation(api, owner, assist["service_session_id"])
    api.post(f"{application}/confirmation-code", headers=auth(owner))
    inbox = api.get(f"{application}/demo-inbox", headers=auth(owner)).json()
    sms_code = re.search(r"код подтверждения (\d{4})", inbox[0]["text"]).group(1)

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
            helper_ws.receive_json()
            owner_ws.receive_json()

            api.post(f"{application}/submit", json={"confirmation_code": sms_code}, headers=auth(owner))

            received = {}
            for name, ws in (("owner", owner_ws), ("helper", helper_ws)):
                received[name] = (ws.receive_json(), ws.receive_json(), closed_code(ws))

    view = api.get(f"/api/v1/assist-sessions/{assist['id']}", headers=auth(owner)).json()
    assert received["owner"][0]["payload"]["application_number"].startswith("ЖКУ-")
    assert received["helper"][0]["payload"]["application_number"] is None
    for submitted, ended, close_code in received.values():
        assert submitted["event"] == "form.submitted"
        assert (ended["event"], ended["payload"]["reason"]) == ("session.ended", "service_submitted")
        assert ended["seq"] == submitted["seq"] + 1
        assert close_code == 4009
    assert (view["status"], view["end_reason"]) == ("ended", "service_submitted")


def test_waiting_person_does_not_see_form_changes(api):
    owner, assist = owner_with_assist(api)
    waiting, participant_id = request_to_join(api, owner, assist["id"], "oleg")
    application = f"/api/v1/service-sessions/{assist['service_session_id']}"

    with api.websocket_connect(socket_url(assist["id"], waiting)) as waiting_ws:
        waiting_ws.receive_json()
        api.patch(
            f"{application}/fields",
            json={"values": {"benefit_category": "pensioner"}},
            headers=auth(owner),
        )
        api.post(f"{application}/navigation", json={"action": "next"}, headers=auth(owner))
        api.post(
            f"/api/v1/assist-sessions/{assist['id']}/participants/{participant_id}/reject",
            headers=auth(owner),
        )
        first = waiting_ws.receive_json()

    assert first["event"] == "participant.status_changed"


def test_cancelling_the_application_ends_the_assist_session(api):
    owner, assist = owner_with_assist(api)
    waiting, _ = request_to_join(api, owner, assist["id"], "oleg")

    with api.websocket_connect(socket_url(assist["id"], waiting)) as waiting_ws:
        waiting_ws.receive_json()
        api.post(f"/api/v1/service-sessions/{assist['service_session_id']}/cancel", headers=auth(owner))
        ended = waiting_ws.receive_json()
        assert closed_code(waiting_ws) == 4009

    assert (ended["event"], ended["payload"]["reason"]) == ("session.ended", "cancelled")


def highlight(ws, element_id, request_id="c-1", label=None, kind="highlight"):
    ws.send_json(
        {
            "command": f"annotation.{kind}",
            "request_id": request_id,
            "payload": {"element_id": element_id, "label": label},
        }
    )


def test_helper_shows_an_element_and_owner_sees_it(api):
    owner, assist = owner_with_assist(api)
    helper, _ = active_helper(api, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
            helper_ws.receive_json()
            owner_ws.receive_json()

            highlight(helper_ws, "benefit_category", label="Нажмите сюда")
            created = owner_ws.receive_json()
            ack = helper_ws.receive_json()

        with api.websocket_connect(socket_url(assist["id"], owner)) as second_tab:
            snapshot = second_tab.receive_json()

    assert created["event"] == "annotation.created"
    assert created["seq"] is None
    assert created["payload"]["element_id"] == "benefit_category"
    assert created["payload"]["label"] == "Нажмите сюда"
    assert created["payload"]["author"]["display_name"] == "Сергей К."
    assert created["payload"]["expires_at"] is not None
    assert ack["event"] == "ack"
    assert ack["payload"]["request_id"] == "c-1"
    assert ack["payload"]["result"]["annotation_id"] == created["payload"]["id"]
    assert [item["element_id"] for item in snapshot["payload"]["annotations"]] == ["benefit_category"]


def test_owner_and_waiting_person_cannot_annotate(api):
    owner, assist = owner_with_assist(api)
    waiting, _ = request_to_join(api, owner, assist["id"], "oleg")

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        highlight(owner_ws, "benefit_category", request_id="o-1")
        owner_error = owner_ws.receive_json()

    with api.websocket_connect(socket_url(assist["id"], waiting)) as waiting_ws:
        waiting_ws.receive_json()
        highlight(waiting_ws, "benefit_category", request_id="w-1")
        waiting_error = waiting_ws.receive_json()

    assert (owner_error["payload"]["request_id"], owner_error["payload"]["code"]) == ("o-1", "forbidden")
    assert (waiting_error["payload"]["request_id"], waiting_error["payload"]["code"]) == ("w-1", "forbidden")


def test_annotation_is_checked_against_the_current_step(api):
    owner, assist = owner_with_assist(api)
    helper, _ = active_helper(api, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
        helper_ws.receive_json()
        highlight(helper_ws, "snils", request_id="c-1")
        unknown = helper_ws.receive_json()
        highlight(helper_ws, "benefit_category", request_id="c-2", label="х" * 81)
        long_label = helper_ws.receive_json()

    assert unknown["payload"]["code"] == "unknown_element"
    assert long_label["payload"]["code"] == "bad_payload"


def test_helper_clears_own_annotations(api):
    owner, assist = owner_with_assist(api)
    helper, _ = active_helper(api, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
            helper_ws.receive_json()
            owner_ws.receive_json()

            highlight(helper_ws, "benefit_category", request_id="1")
            first = owner_ws.receive_json()
            helper_ws.receive_json()

            helper_ws.send_json(
                {
                    "command": "annotation.clear",
                    "request_id": "2",
                    "payload": {"annotation_id": first["payload"]["id"]},
                }
            )
            cleared = owner_ws.receive_json()
            helper_ws.receive_json()

            highlight(helper_ws, "benefit_reason", request_id="3")
            owner_ws.receive_json()
            helper_ws.receive_json()

            helper_ws.send_json({"command": "annotation.clear", "request_id": "4", "payload": {}})
            cleared_rest = owner_ws.receive_json()
            helper_ws.receive_json()

    assert cleared["event"] == "annotation.cleared"
    assert cleared["payload"]["annotation_ids"] == [first["payload"]["id"]]
    assert len(cleared_rest["payload"]["annotation_ids"]) == 1


def test_pointer_reaches_owner_without_a_reply(api):
    owner, assist = owner_with_assist(api)
    helper, _ = active_helper(api, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
            helper_ws.receive_json()
            owner_ws.receive_json()

            helper_ws.send_json(
                {
                    "command": "annotation.pointer",
                    "payload": {"element_id": "benefit_category", "rel_x": 0.42, "rel_y": 2},
                }
            )
            pointer = owner_ws.receive_json()

            helper_ws.send_json({"command": "helper.message", "request_id": "c-9", "payload": {}})
            reply = helper_ws.receive_json()

    assert pointer["event"] == "annotation.pointer"
    assert pointer["payload"] == {
        "element_id": "benefit_category",
        "rel_x": 0.42,
        "rel_y": 1.0,
        "visible": True,
    }
    assert reply["payload"]["code"] == "unknown_command"


def test_step_change_clears_annotations(api):
    owner, assist = owner_with_assist(api)
    helper, _ = active_helper(api, owner, assist["id"])
    application = f"/api/v1/service-sessions/{assist['service_session_id']}"

    with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
        helper_ws.receive_json()
        highlight(helper_ws, "benefit_category")
        helper_ws.receive_json()

        api.patch(f"{application}/fields", json={"values": STEP_VALUES["category"]}, headers=auth(owner))
        helper_ws.receive_json()
        api.post(f"{application}/navigation", json={"action": "next"}, headers=auth(owner))
        helper_ws.receive_json()

    with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
        snapshot = helper_ws.receive_json()

    assert snapshot["payload"]["current_step"]["id"] == "address"
    assert snapshot["payload"]["annotations"] == []


def test_annotations_are_rate_limited(api):
    owner, assist = owner_with_assist(api)
    helper, _ = active_helper(api, owner, assist["id"])

    answers = []
    with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
        helper_ws.receive_json()
        for index in range(8):
            highlight(helper_ws, "benefit_category", request_id=str(index))
        for _ in range(8):
            message = helper_ws.receive_json()
            answers.append(message["payload"].get("code", message["event"]))

    assert answers.count("ack") >= 1
    assert answers.count("rate_limited") >= 1


def send(ws, command, payload, request_id="c-1"):
    ws.send_json({"command": command, "request_id": request_id, "payload": payload})


def test_owner_hears_that_helper_is_busy(api):
    owner, assist = owner_with_assist(api)
    helper = login(api, "sergey")
    token = api.post(
        f"/api/v1/assist-sessions/{assist['id']}/invites",
        json={"kind": "link"},
        headers=auth(owner),
    ).json()["token"]

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        snapshot = owner_ws.receive_json()
        declined = api.post(f"/api/v1/assist-invites/{token}/decline", headers=auth(helper)).json()
        event = owner_ws.receive_json()

    assert event["event"] == "invite.declined"
    assert event["seq"] == snapshot["payload"]["last_seq"] + 1
    assert event["payload"]["helper"] == {"display_name": "Сергей К."}
    assert event["payload"]["help_callback_id"] == declined["help_callback_id"]


def test_owner_follows_the_operator_queue(api):
    owner, assist = owner_with_assist(api)
    anna = login(api, "anna")

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        request = api.post(
            f"/api/v1/assist-sessions/{assist['id']}/operator-requests",
            json={"topic": "dont_understand"},
            headers=auth(owner),
        ).json()
        queued = next_event(owner_ws, "operator_request.updated")
        api.post(f"/api/v1/operator/requests/{request['id']}/claim", headers=auth(anna))
        claimed = next_event(owner_ws, "operator_request.updated")

    assert queued["payload"]["status"] == "queued"
    assert queued["payload"]["position"] == request["position"]
    assert claimed["payload"] == {**queued["payload"], "status": "claimed", "position": None}


def next_event(ws, name):
    while True:
        message = ws.receive_json()
        if message["event"] == name:
            return message


def test_owner_marks_what_is_unclear(api):
    owner, assist = owner_with_assist(api)
    helper, _ = active_helper(api, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], helper)) as helper_ws:
            helper_ws.receive_json()
            owner_ws.receive_json()

            send(owner_ws, "owner.flag_confusion", {"element_id": "benefit_reason"}, "f-1")
            flagged = helper_ws.receive_json()
            owner_ack = owner_ws.receive_json()

            send(helper_ws, "owner.flag_confusion", {"element_id": "benefit_reason"}, "f-2")
            helper_denied = helper_ws.receive_json()

    assert flagged["event"] == "owner.confusion_flagged"
    assert flagged["payload"] == {"element_id": "benefit_reason"}
    assert flagged["actor"]["role"] == "owner"
    assert owner_ack["event"] == "ack"
    assert helper_denied["payload"]["code"] == "forbidden"


def test_socket_closed_during_handshake_leaks_no_connections(api):
    owner, assist = owner_with_assist(api)
    helper, _ = active_helper(api, owner, assist["id"])

    for _ in range(30):
        with api.websocket_connect(socket_url(assist["id"], owner)):
            pass
        with api.websocket_connect(socket_url(assist["id"], helper)):
            pass

    api.portal.call(settle)
    gc.collect()

from datetime import timedelta
from uuid import uuid4

import pytest

from max_assist.errors import Conflict, Forbidden, Gone, NotFound, Unprocessable
from max_assist.modules.assist import domain
from max_assist.modules.identity.models import User
from max_assist.utils import now


def person(first_name: str, last_name: str = "Тестов", agreed: bool = True) -> User:
    return User(
        id=uuid4(),
        first_name=first_name,
        last_name=last_name,
        recording_consent_at=now() if agreed else None,
    )


@pytest.fixture
def owner():
    return person("Людмила", "Петрова")


@pytest.fixture
def session(owner):
    return domain.start(owner, uuid4(), "housing_compensation", 1)


def joined(session, owner, user, is_trusted=False):
    invite, _ = domain.create_invite(session, owner)
    return domain.accept_invite(session, invite, user, is_trusted)


def test_new_session_waits_with_owner_inside(session, owner):
    [participant] = session.participants

    assert session.status == "waiting"
    assert (participant.user_id, participant.role, participant.status) == (owner.id, "owner", "active")


def test_help_is_not_called_without_consent_to_record():
    with pytest.raises(Conflict) as error:
        domain.start(person("Людмила", agreed=False), uuid4(), "housing_compensation", 1)

    assert error.value.code == "recording_consent_required"


def test_helper_without_consent_keeps_the_invite_unused(session, owner):
    invite, _ = domain.create_invite(session, owner)

    with pytest.raises(Conflict) as error:
        domain.accept_invite(session, invite, person("Сергей", agreed=False))

    assert error.value.code == "recording_consent_required"
    assert invite.used_at is None
    assert len(session.participants) == 1


def test_invite_keeps_only_token_hash(session, owner):
    invite, token = domain.create_invite(session, owner)

    assert invite.token_hash == domain.hash_token(token)
    assert token not in invite.token_hash
    assert invite.expires_at - invite.created_at == domain.INVITE_TTL


def test_only_owner_can_invite(session):
    with pytest.raises(Forbidden):
        domain.create_invite(session, person("Олег"))


def test_stranger_waits_for_owner_approval(session, owner):
    oleg = person("Олег")

    participant = joined(session, owner, oleg)

    assert (participant.role, participant.status) == ("invited_helper", "pending")
    assert participant.badge_label == "Помощник по ссылке"
    assert session.status == "waiting"
    assert session.invites[0].used_by == oleg.id


def test_trusted_helper_joins_at_once(session, owner):
    participant = joined(session, owner, person("Сергей"), is_trusted=True)

    assert (participant.role, participant.status) == ("trusted_helper", "active")
    assert session.status == "active"
    assert session.started_at is not None


def test_owner_cannot_join_as_helper(session, owner):
    invite, _ = domain.create_invite(session, owner)

    with pytest.raises(Unprocessable) as error:
        domain.accept_invite(session, invite, owner)

    assert error.value.code == "owner_cannot_join"


def test_invite_works_only_once(session, owner):
    invite, _ = domain.create_invite(session, owner)
    domain.accept_invite(session, invite, person("Сергей"))

    with pytest.raises(Gone) as error:
        domain.accept_invite(session, invite, person("Олег"))

    assert error.value.code == "invite_used"


def test_expired_invite_is_rejected(session, owner):
    invite, _ = domain.create_invite(session, owner)
    invite.expires_at = now() - timedelta(seconds=1)

    with pytest.raises(Gone) as error:
        domain.accept_invite(session, invite, person("Сергей"))

    assert error.value.code == "invite_expired"


def test_revoked_invite_is_rejected(session, owner):
    invite, _ = domain.create_invite(session, owner)
    invite.revoked_at = now()

    with pytest.raises(Gone) as error:
        domain.accept_invite(session, invite, person("Сергей"))

    assert error.value.code == "invite_revoked"


def test_invite_of_another_session_is_rejected(owner):
    first = domain.start(owner, uuid4(), "housing_compensation", 1)
    second = domain.start(owner, uuid4(), "housing_compensation", 1)
    invite, _ = domain.create_invite(first, owner)

    with pytest.raises(NotFound):
        domain.accept_invite(second, invite, person("Сергей"))


def test_same_person_cannot_join_twice(session, owner):
    sergey = person("Сергей")
    joined(session, owner, sergey)

    with pytest.raises(Conflict) as error:
        joined(session, owner, sergey)

    assert error.value.code == "already_participant"


def test_helpers_limit(session, owner):
    joined(session, owner, person("Сергей"), is_trusted=True)
    joined(session, owner, person("Анна"), is_trusted=True)

    with pytest.raises(Conflict) as error:
        joined(session, owner, person("Олег"), is_trusted=True)

    assert error.value.code == "helpers_limit_reached"


def test_limit_is_checked_again_on_approval(session, owner):
    waiting = joined(session, owner, person("Олег"))
    joined(session, owner, person("Сергей"), is_trusted=True)
    joined(session, owner, person("Анна"), is_trusted=True)

    with pytest.raises(Conflict) as error:
        domain.approve(session, owner, waiting.id)

    assert error.value.code == "helpers_limit_reached"
    assert waiting.status == "pending"


def test_owner_approval_starts_the_session(session, owner):
    waiting = joined(session, owner, person("Олег"))

    domain.approve(session, owner, waiting.id)

    assert waiting.status == "active"
    assert waiting.joined_at is not None
    assert session.status == "active"


def test_only_owner_approves(session, owner):
    oleg = person("Олег")
    waiting = joined(session, owner, oleg)

    with pytest.raises(Forbidden):
        domain.approve(session, oleg, waiting.id)


def test_approving_twice_is_rejected(session, owner):
    waiting = joined(session, owner, person("Олег"))
    domain.approve(session, owner, waiting.id)

    with pytest.raises(Conflict) as error:
        domain.approve(session, owner, waiting.id)

    assert error.value.code == "participant_not_pending"


def test_unknown_participant_is_not_found(session, owner):
    with pytest.raises(NotFound):
        domain.approve(session, owner, uuid4())


def test_rejected_person_can_come_back_with_new_invite(session, owner):
    oleg = person("Олег")
    first = joined(session, owner, oleg)
    domain.reject(session, owner, first.id)
    assert first.status == "rejected"

    second = joined(session, owner, oleg)

    assert second is first
    assert second.status == "pending"
    assert second.left_at is None
    assert len(session.participants) == 2


def test_rejecting_active_helper_is_not_allowed(session, owner):
    helper = joined(session, owner, person("Сергей"), is_trusted=True)

    with pytest.raises(Conflict):
        domain.reject(session, owner, helper.id)


def test_owner_removes_helper_and_cannot_be_removed(session, owner):
    helper = joined(session, owner, person("Сергей"), is_trusted=True)

    domain.remove(session, owner, helper.id)

    assert helper.status == "removed"
    with pytest.raises(Unprocessable) as error:
        domain.remove(session, owner, session.participants[0].id)
    assert error.value.code == "owner_cannot_be_removed"


def test_removing_pending_helper_is_not_allowed(session, owner):
    waiting = joined(session, owner, person("Олег"))

    with pytest.raises(Conflict) as error:
        domain.remove(session, owner, waiting.id)

    assert error.value.code == "participant_not_active"


def test_helper_leaves_but_owner_cannot(session, owner):
    sergey = person("Сергей")
    helper = joined(session, owner, sergey, is_trusted=True)

    domain.leave(session, sergey)

    assert helper.status == "left"
    assert session.status == "active"
    with pytest.raises(Unprocessable) as error:
        domain.leave(session, owner)
    assert error.value.code == "owner_cannot_leave"


def test_stranger_cannot_leave(session):
    with pytest.raises(NotFound):
        domain.leave(session, person("Олег"))


def test_end_disconnects_everyone_and_revokes_invites(session, owner):
    helper = joined(session, owner, person("Сергей"), is_trusted=True)
    waiting = joined(session, owner, person("Олег"))
    open_invite, _ = domain.create_invite(session, owner)

    domain.end_by_owner(session, owner)

    assert (session.status, session.end_reason) == ("ended", "owner_ended")
    assert session.ended_at is not None
    assert (helper.status, waiting.status) == ("left", "left")
    assert session.participants[0].status == "active"
    assert open_invite.revoked_at is not None


def test_ended_session_is_closed_for_everything(session, owner):
    invite, _ = domain.create_invite(session, owner)
    domain.end(session, "expired")

    with pytest.raises(Gone):
        domain.accept_invite(session, invite, person("Сергей"))
    with pytest.raises(Gone):
        domain.create_invite(session, owner)
    with pytest.raises(Gone) as error:
        domain.end_by_owner(session, owner)
    assert error.value.code == "session_ended"


def test_only_owner_ends(session):
    with pytest.raises(Forbidden):
        domain.end_by_owner(session, person("Олег"))


def test_revoked_invite_is_no_longer_open(session, owner):
    invite, _ = domain.create_invite(session, owner)

    domain.revoke_invite(session, owner, invite.id)
    domain.revoke_invite(session, owner, invite.id)

    assert domain.invite_status(session, invite) == "revoked"
    assert domain.open_invites(session) == []


def test_used_invite_cannot_be_revoked(session, owner):
    invite, _ = domain.create_invite(session, owner)
    domain.accept_invite(session, invite, person("Сергей"))

    with pytest.raises(Conflict) as error:
        domain.revoke_invite(session, owner, invite.id)

    assert error.value.code == "invite_used"


def test_unknown_invite_cannot_be_revoked(session, owner):
    with pytest.raises(NotFound):
        domain.revoke_invite(session, owner, uuid4())


def test_ended_session_is_reported_before_invite_state(session, owner):
    invite, _ = domain.create_invite(session, owner)

    domain.end(session, "expired")

    assert domain.invite_status(session, invite) == "session_ended"


def test_helpers_do_not_manage_and_do_not_see_sensitive_values():
    owner = domain.capabilities_of("owner")

    for role in ("trusted_helper", "invited_helper", "government_operator", "ai_agent"):
        helper = domain.capabilities_of(role)
        assert "view_sensitive_values" not in helper
        assert not {"invite", "end_session", "submit", "edit_fields", "navigate"} & helper

    assert {"view_sensitive_values", "submit", "invite"} <= owner
    assert "view_operator_hints" not in domain.capabilities_of("invited_helper")
    assert "view_operator_hints" in domain.capabilities_of("government_operator")

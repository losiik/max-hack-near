from datetime import timedelta
from uuid import uuid4

from max_assist.modules.assist import domain
from max_assist.modules.assist.annotations import HIGHLIGHT_TTL, MAX_PER_AUTHOR, AnnotationBoard
from max_assist.modules.assist.limits import RateLimiter
from max_assist.modules.assist.schemas import annotation_out
from max_assist.modules.identity.models import User
from max_assist.utils import now


def test_new_highlight_replaces_the_previous_one_of_the_same_helper():
    board = AnnotationBoard()
    session, sergey, anna = uuid4(), uuid4(), uuid4()

    board.add(session, sergey, "highlight", "snils", None)
    board.add(session, anna, "highlight", "address", None)
    board.add(session, sergey, "highlight", "family_size", None)

    assert [(item.author_participant_id, item.element_id) for item in board.active(session)] == [
        (anna, "address"),
        (sergey, "family_size"),
    ]


def test_highlight_expires_and_other_kinds_stay():
    board = AnnotationBoard()
    session, sergey = uuid4(), uuid4()

    highlight = board.add(session, sergey, "highlight", "snils", None)
    frame = board.add(session, sergey, "frame", "address", None)

    assert highlight.expires_at - highlight.created_at == HIGHLIGHT_TTL
    assert frame.expires_at is None

    highlight.expires_at = now() - timedelta(seconds=1)
    assert [item.kind for item in board.active(session)] == ["frame"]


def test_oldest_annotation_is_dropped_above_the_limit():
    board = AnnotationBoard()
    session, sergey = uuid4(), uuid4()

    for index in range(MAX_PER_AUTHOR + 2):
        board.add(session, sergey, "frame", f"element_{index}", None)

    alive = board.active(session)
    assert len(alive) == MAX_PER_AUTHOR
    assert [item.element_id for item in alive][0] == "element_2"


def test_helper_clears_only_own_annotations():
    board = AnnotationBoard()
    session, sergey, anna = uuid4(), uuid4(), uuid4()
    board.add(session, sergey, "frame", "snils", None)
    board.add(session, anna, "frame", "address", None)

    removed = board.clear(session, sergey)

    assert [item.element_id for item in removed] == ["snils"]
    assert [item.author_participant_id for item in board.active(session)] == [anna]


def test_single_annotation_can_be_cleared_by_id():
    board = AnnotationBoard()
    session, sergey = uuid4(), uuid4()
    first = board.add(session, sergey, "frame", "snils", None)
    board.add(session, sergey, "arrow", "address", None)

    removed = board.clear(session, sergey, first.id)

    assert [item.id for item in removed] == [first.id]
    assert [item.kind for item in board.active(session)] == ["arrow"]
    assert board.clear(session, sergey, first.id) == []


def test_step_change_wipes_annotations_and_known_elements():
    board = AnnotationBoard()
    session, sergey = uuid4(), uuid4()
    board.add(session, sergey, "frame", "snils", None)
    board.remember_elements(session, {"snils"})

    board.clear_step(session)

    assert board.active(session) == []
    assert board.known_elements(session) is None


def test_board_forgets_sessions_without_annotations():
    board = AnnotationBoard()
    session, sergey = uuid4(), uuid4()

    board.add(session, sergey, "frame", "snils", None)
    board.clear(session, sergey)
    assert session not in board.annotations

    highlight = board.add(session, sergey, "highlight", "snils", None)
    highlight.expires_at = now() - timedelta(seconds=1)
    board.active(session)
    assert session not in board.annotations


def test_annotation_of_a_gone_participant_is_skipped():
    owner = User(id=uuid4(), first_name="Людмила", last_name="Петрова", recording_consent_at=now())
    assist = domain.start(owner, uuid4(), "housing_compensation", 1)
    board = AnnotationBoard()
    session = uuid4()
    mine = board.add(session, assist.participants[0].id, "frame", "snils", None)
    stranger = board.add(session, uuid4(), "frame", "address", None)

    assert annotation_out(mine, assist).element_id == "snils"
    assert annotation_out(stranger, assist) is None


def test_rate_limiter_allows_a_burst_then_blocks_and_refills():
    limiter = RateLimiter(per_second=3, burst=3)

    assert [limiter.allow("helper") for _ in range(4)] == [True, True, True, False]

    limiter.buckets["helper"].updated = now() - timedelta(seconds=1)

    assert limiter.allow("helper") is True


def test_rate_limiter_counts_every_key_on_its_own():
    limiter = RateLimiter(per_second=1, burst=1)

    assert limiter.allow("first") is True
    assert limiter.allow("first") is False
    assert limiter.allow("second") is True

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from max_assist.utils import now

KINDS = {"highlight", "frame", "circle", "arrow"}
HIGHLIGHT_TTL = timedelta(seconds=15)
LABEL_LIMIT = 80
MAX_PER_AUTHOR = 5


@dataclass
class Annotation:
    id: uuid.UUID
    author_participant_id: uuid.UUID
    kind: str
    element_id: str
    label: str | None
    created_at: datetime
    expires_at: datetime | None


class AnnotationBoard:
    def __init__(self) -> None:
        self.annotations: dict[uuid.UUID, list[Annotation]] = {}
        self.elements: dict[uuid.UUID, set[str]] = {}

    def active(self, assist_id: uuid.UUID) -> list[Annotation]:
        moment = now()
        alive = [
            item
            for item in self.annotations.get(assist_id, [])
            if item.expires_at is None or item.expires_at > moment
        ]
        if alive:
            self.annotations[assist_id] = alive
        else:
            self.annotations.pop(assist_id, None)
        return alive

    def add(
        self,
        assist_id: uuid.UUID,
        author_participant_id: uuid.UUID,
        kind: str,
        element_id: str,
        label: str | None,
    ) -> Annotation:
        moment = now()
        annotation = Annotation(
            id=uuid.uuid4(),
            author_participant_id=author_participant_id,
            kind=kind,
            element_id=element_id,
            label=label,
            created_at=moment,
            expires_at=moment + HIGHLIGHT_TTL if kind == "highlight" else None,
        )

        alive = []
        for item in self.active(assist_id):
            # новая подсветка заменяет предыдущую того же помощника
            same_highlight = kind == "highlight" and item.kind == "highlight"
            if same_highlight and item.author_participant_id == author_participant_id:
                continue
            alive.append(item)
        alive.append(annotation)

        mine = [item for item in alive if item.author_participant_id == author_participant_id]
        while len(mine) > MAX_PER_AUTHOR:
            alive.remove(mine.pop(0))

        self.annotations[assist_id] = alive
        return annotation

    def clear(
        self,
        assist_id: uuid.UUID,
        author_participant_id: uuid.UUID,
        annotation_id: uuid.UUID | None = None,
    ) -> list[Annotation]:
        alive = self.active(assist_id)
        removed = [
            item
            for item in alive
            if item.author_participant_id == author_participant_id
            and (annotation_id is None or item.id == annotation_id)
        ]
        left = [item for item in alive if item not in removed]
        if left:
            self.annotations[assist_id] = left
        else:
            self.annotations.pop(assist_id, None)
        return removed

    def clear_step(self, assist_id: uuid.UUID) -> None:
        self.annotations.pop(assist_id, None)
        self.elements.pop(assist_id, None)

    def remember_elements(self, assist_id: uuid.UUID, element_ids: set[str]) -> None:
        self.elements[assist_id] = element_ids

    def known_elements(self, assist_id: uuid.UUID) -> set[str] | None:
        return self.elements.get(assist_id)


board = AnnotationBoard()

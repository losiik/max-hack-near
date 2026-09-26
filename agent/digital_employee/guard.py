import re
from collections.abc import Iterable

# около 13 секунд речи: дольше пожилой человек не удержит объяснение в голове
MAX_LENGTH = 200
FALLBACK = "Давайте я лучше покажу на форме."

# четыре цифры и больше, в том числе через пробел или дефис: так выглядят СНИЛС, счёт, коды
DIGITS = re.compile(r"\d(?:[\s\-]?\d){3,}")
ASK_SECRET = re.compile(
    r"(назов|назвать|продикт|диктов|сообщ|скаж|прочит|озвуч|повтор)\w*[^.!?]{0,60}?"
    r"(код|парол|снилс|карт|сч[её]т|паспорт|пин)",
    re.IGNORECASE,
)
SENTENCE_END = re.compile(r"[.!?…]+[\s»\"]*|\n+")


class AnswerGuard:
    def __init__(self, public_texts: Iterable[str] = ()) -> None:
        # подсказки формата из описания услуги публичны, их можно произносить
        self.public = [text for text in public_texts if text]

    def is_public(self, digits: str) -> bool:
        return any(digits in text for text in self.public)

    def problem(self, sentence: str) -> str | None:
        for match in DIGITS.finditer(sentence):
            if not self.is_public(match.group()):
                return "digits"
        if ASK_SECRET.search(sentence):
            return "asks_secret"
        return None


class GuardedReply:
    # ответ модели идёт кусками: собираем предложения и пропускаем дальше только проверенные
    def __init__(self, guard: AnswerGuard) -> None:
        self.guard = guard
        self.buffer = ""
        self.spoken = ""
        self.rejected = False
        self.stopped = False

    def feed(self, text: str) -> list[str]:
        if self.stopped:
            return []
        self.buffer += text
        ready = []
        while True:
            match = SENTENCE_END.search(self.buffer)
            if match is None:
                break
            sentence, self.buffer = self.buffer[: match.end()], self.buffer[match.end() :]
            ready.extend(self.accept(sentence))
            if self.stopped:
                break
        return ready

    def finish(self) -> list[str]:
        rest, self.buffer = self.buffer, ""
        if rest.strip() and not self.stopped:
            return self.accept(rest)
        return []

    def accept(self, sentence: str) -> list[str]:
        if not sentence.strip():
            return []
        if self.guard.problem(sentence):
            self.rejected = True
            self.stopped = True
            return [FALLBACK]
        if self.spoken and len(self.spoken) + len(sentence) > MAX_LENGTH:
            # первое предложение договариваем всегда, а дальше обрываем на границе предложения
            self.stopped = True
            return []
        if self.spoken and not self.spoken[-1].isspace() and not sentence[0].isspace():
            self.spoken += " "
        self.spoken += sentence
        return [sentence]

    @property
    def text(self) -> str:
        said = self.spoken.strip()
        return f"{said} {FALLBACK}".strip() if self.rejected else said

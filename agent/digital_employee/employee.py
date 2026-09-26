import asyncio
import logging
import time
from collections import Counter
from collections.abc import AsyncIterable
from typing import Any

from livekit.agents import (
    Agent,
    AgentStateChangedEvent,
    FlushSentinel,
    FunctionToolsExecutedEvent,
    ModelSettings,
    RunContext,
    UserStateChangedEvent,
    function_tool,
    llm,
)

from digital_employee import prompts
from digital_employee.backend import Backend
from digital_employee.form import HUMAN_ROLES, FormState
from digital_employee.guard import AnswerGuard, GuardedReply

logger = logging.getLogger("digital_employee")


class DigitalEmployee(Agent):
    def __init__(self, backend: Backend, form: FormState, provider: str) -> None:
        super().__init__(instructions=prompts.instructions(form.describe()))
        self.backend = backend
        self.form = form
        self.provider = provider
        self.trigger = "greeting"
        self.asked_at = time.monotonic()
        self.tools_used: list[dict[str, Any]] = []
        self.pending: dict[str, Any] | None = None
        self.spoke_at = 0.0
        self.answered = False
        self.confusions: Counter[str] = Counter()
        self.leaving = False
        self.tasks: set[asyncio.Task] = set()

    async def on_enter(self) -> None:
        self.ask("greeting", prompts.GREETING)

    def ask(self, trigger: str, instructions: str) -> None:
        self.trigger = trigger
        self.asked_at = time.monotonic()
        self.session.generate_reply(instructions=instructions)

    def on_user_state(self, event: UserStateChangedEvent) -> None:
        # человек договорил: следующий ответ — на его вопрос, задержку считаем отсюда
        if event.old_state == "speaking":
            self.trigger = "question"
            self.asked_at = time.monotonic()

    async def llm_node(
        self,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        model_settings: ModelSettings,
    ) -> AsyncIterable[llm.ChatChunk | str | FlushSentinel]:
        # проверка стоит до синтеза и до расшифровки: непрошедший текст не прозвучит и не появится на экране
        reply = GuardedReply(AnswerGuard(self.form.public_texts()))
        trigger, asked_at = self.trigger, self.asked_at
        self.answered = False
        async for chunk in Agent.default.llm_node(self, chat_ctx, tools, model_settings):
            if isinstance(chunk, str):
                text = chunk
            elif isinstance(chunk, llm.ChatChunk) and chunk.delta is not None:
                text = chunk.delta.content
                if chunk.delta.tool_calls:
                    yield llm.ChatChunk(
                        id=chunk.id,
                        delta=llm.ChoiceDelta(role="assistant", tool_calls=chunk.delta.tool_calls),
                    )
            else:
                continue
            for sentence in reply.feed(text or ""):
                self.answered = True
                yield sentence
                # предложение уже проверено — синтез может начинать, не дожидаясь следующего
                yield FlushSentinel()
        for sentence in reply.finish():
            self.answered = True
            yield sentence

        if reply.text:
            self.pending = {
                "trigger": trigger,
                "reply_text": reply.text,
                "guard_result": "rejected" if reply.rejected else "passed",
                "asked_at": asked_at,
            }
            # длинный ответ начинает звучать раньше, чем модель его договорит
            if self.spoke_at >= asked_at:
                self.pending["latency_ms"] = int((self.spoke_at - asked_at) * 1000)

    def on_agent_state(self, event: AgentStateChangedEvent) -> None:
        if event.new_state == "speaking":
            self.spoke_at = time.monotonic()
        if self.pending is None:
            return
        if event.new_state == "speaking" and "latency_ms" not in self.pending:
            self.pending["latency_ms"] = int((self.spoke_at - self.pending["asked_at"]) * 1000)
        elif event.old_state == "speaking":
            self.save_turn()

    def on_tools_executed(self, event: FunctionToolsExecutedEvent) -> None:
        # подсветку модель обычно делает вместе с ответом; второй раз говорить «я подсветила» не нужно
        if self.answered and all(call.name in ("highlight", "point") for call in event.function_calls):
            event.cancel_tool_reply()

    def save_turn(self) -> None:
        turn, self.pending = self.pending, None
        tools, self.tools_used = self.tools_used, []
        turn.pop("asked_at")
        turn.setdefault("latency_ms", 0)
        turn.update(tools=tools, provider=self.provider)
        logger.info("%s answered in %s ms, tools %s", turn["trigger"], turn["latency_ms"], tools)
        task = asyncio.create_task(self.backend.record_turn(turn))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    @function_tool
    async def highlight(self, context: RunContext, element_id: str) -> str:
        """Подсветить поле на экране человека, чтобы он увидел, куда нажать.

        Args:
            element_id: id поля текущего шага из описания экрана
        """
        if element_id not in self.form.element_ids():
            return "Такого поля нет на текущем шаге"
        await self.backend.highlight(element_id)
        self.tools_used.append({"name": "highlight", "element_id": element_id})
        return f"Поле «{self.form.label(element_id)}» подсвечено"

    @function_tool
    async def point(self, context: RunContext, element_id: str) -> str:
        """Показать поле указателем.

        Args:
            element_id: id поля текущего шага из описания экрана
        """
        if element_id not in self.form.element_ids():
            return "Такого поля нет на текущем шаге"
        await self.backend.point(element_id)
        self.tools_used.append({"name": "point", "element_id": element_id})
        return f"Указатель на поле «{self.form.label(element_id)}»"

    @function_tool
    async def call_operator(self, context: RunContext, summary: str) -> str:
        """Позвать живого сотрудника МФЦ, когда человек согласился.

        Args:
            summary: одно-два предложения о том, где человек и в чём трудность, без личных данных
        """
        # резюме увидит сотрудник, поэтому проверяем его так же, как речь
        if AnswerGuard(self.form.public_texts()).problem(summary) or len(summary) > 500:
            summary = f"Нужна помощь на шаге «{self.form.step['title']}»."
        called = await self.backend.call_operator(summary)
        self.tools_used.append({"name": "call_operator", "element_id": None})
        if not called:
            return "Позвать сотрудника не получилось. Скажи человеку, что можно попробовать позже."
        return "Сотрудник МФЦ вызван. Скажи человеку, что он скоро подключится, а пока ты рядом."

    async def on_backend_event(self, message: dict[str, Any]) -> None:
        event, payload = message["event"], message.get("payload") or {}
        self.form.apply(event, payload)
        if event in ("navigation.step_changed", "form.field_updated", "form.validation_failed"):
            await self.update_instructions(prompts.instructions(self.form.describe()))
        if self.leaving:
            return

        if event == "participant.joined" and payload["participant"]["role"] in HUMAN_ROLES:
            await self.hand_over(payload["participant"]["display_name"])
        elif event == "form.validation_failed" and payload.get("errors"):
            self.ask("validation_failed", prompts.VALIDATION_FAILED)
        elif event == "owner.confusion_flagged":
            element_id = payload["element_id"]
            self.confusions[element_id] += 1
            text = prompts.CONFUSION_AGAIN if self.confusions[element_id] > 1 else prompts.CONFUSION
            self.ask("confusion", text.format(label=self.form.label(element_id)))
        elif event == "navigation.step_changed":
            self.ask("step_changed", prompts.STEP_CHANGED.format(title=self.form.step["title"]))

    async def hand_over(self, name: str) -> None:
        # два помощника, говорящие одновременно, путают человека: прощаемся и уходим
        self.leaving = True
        self.session.interrupt()
        await self.session.say(prompts.GOODBYE.format(name=name), allow_interruptions=False)
        await self.backend.leave()

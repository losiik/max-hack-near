import json
import logging

from livekit.agents import AgentServer, AgentSession, JobContext, JobProcess, JobRequest, room_io
from livekit.plugins import openai, silero

from digital_employee.backend import Backend
from digital_employee.config import Settings
from digital_employee.employee import DigitalEmployee
from digital_employee.form import FormState
from digital_employee.speechkit import SpeechKitSTT, SpeechKitTTS

logger = logging.getLogger("digital_employee")
settings = Settings()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load(min_silence_duration=settings.silence_seconds)


# встреч с агентом немного, а каждый запасной процесс держит модель VAD в памяти
server = AgentServer(setup_fnc=prewarm, num_idle_processes=1)


async def accept(request: JobRequest) -> None:
    # в комнате агент выступает под id своего участника: так frontend узнаёт его голос,
    # а backend может убрать его из комнаты
    metadata = json.loads(request.job.metadata or "{}")
    if "participant_id" not in metadata:
        await request.reject()
        return
    await request.accept(identity=metadata["participant_id"], name="Цифровой сотрудник")


def log_timings(item: object) -> None:
    # колбэк работает внутри конвейера ответа: он не должен падать ни на каком сообщении
    metrics = getattr(item, "metrics", None) or {}
    numbers = {key: round(value, 2) for key, value in metrics.items() if isinstance(value, float)}
    if numbers:
        logger.info("%s timings %s", getattr(item, "role", "?"), numbers)


def build_session(ctx: JobContext) -> AgentSession:
    return AgentSession(
        stt=SpeechKitSTT(settings.yandex_api_key, settings.yandex_folder_id),
        llm=openai.LLM(
            model=f"gpt://{settings.yandex_folder_id}/{settings.llm_model}",
            base_url=settings.llm_base_url,
            api_key=settings.yandex_api_key,
        ),
        tts=SpeechKitTTS(settings.yandex_api_key, settings.yandex_folder_id, settings.voice),
        vad=ctx.proc.userdata["vad"],
        # конец фразы решает наш VAD с длинной паузой, а текст к этому моменту уже распознан потоком.
        # перебивание — тоже по VAD: облачный детектор LiveKit нам недоступен, и звук туда не уходит
        turn_handling={
            "turn_detection": "vad",
            "endpointing": {"min_delay": 0.0},
            "interruption": {"mode": "vad"},
        },
    )


@server.rtc_session(agent_name=settings.agent_name, on_request=accept)
async def entrypoint(ctx: JobContext) -> None:
    metadata = json.loads(ctx.job.metadata)
    backend = Backend(settings.backend_url, metadata["assist_session_id"], metadata["token"])
    ctx.add_shutdown_callback(backend.close)
    try:
        snapshot = await backend.connect()
    except Exception:
        # пока агент шёл, его могли отпустить или встреча закончилась
        logger.exception("could not join the meeting %s", metadata["assist_session_id"])
        ctx.shutdown(reason="meeting is not available")
        return

    form = FormState()
    form.load(snapshot)
    owner = next(item["id"] for item in snapshot["session"]["participants"] if item["role"] == "owner")

    await ctx.connect()
    session = build_session(ctx)
    employee = DigitalEmployee(backend, form, settings.provider)
    session.on("agent_state_changed", employee.on_agent_state)
    session.on("user_state_changed", employee.on_user_state)
    session.on("function_tools_executed", employee.on_tools_executed)
    # только числа: сколько ушло на распознавание, модель и синтез; текст речи человека в лог не пишем
    session.on("conversation_item_added", lambda event: log_timings(event.item))
    # слушаем только владельца; чата нет, а если он переподключится к голосу — ждём его
    options = room_io.RoomOptions(participant_identity=owner, text_input=False, close_on_disconnect=False)
    await session.start(agent=employee, room=ctx.room, room_options=options)

    async for message in backend.events():
        try:
            await employee.on_backend_event(message)
        except Exception:
            logger.exception("could not handle %s", message.get("event"))

    # backend закрыл сокет: агента отпустили, он ушёл сам или встреча закончилась
    ctx.shutdown(reason="left the meeting")

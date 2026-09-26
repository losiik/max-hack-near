import asyncio
import base64
import json
import logging
import time
from typing import Any

import grpc
import httpx
from livekit import rtc
from livekit.agents import (
    DEFAULT_API_CONNECT_OPTIONS,
    APIConnectionError,
    APIConnectOptions,
    APIStatusError,
    APITimeoutError,
    stt,
    tts,
    utils,
)
from livekit.agents.types import NOT_GIVEN, NotGivenOr
from yandex.cloud.ai.stt.v3 import stt_pb2
from yandex.cloud.ai.stt.v3.stt_service_pb2_grpc import RecognizerStub

logger = logging.getLogger("digital_employee")

STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
STT_HOST = "stt.api.cloud.yandex.net:443"
TTS_URL = "https://tts.api.cloud.yandex.net/tts/v3/utteranceSynthesis"
STT_RATE = 16000
TTS_RATE = 48000
# SpeechKit закрывает кусок фразы после такой паузы; конец всей фразы решает VAD, куски склеит LiveKit
PAUSE_MS = 500
# если поток проработал дольше, его обрыв — это лимит длины или сеть, а не отказ: подключаемся заново
STABLE_SECONDS = 10


def to_mono_16k(buffer: utils.AudioBuffer) -> bytes:
    frame = utils.merge_frames(buffer)
    if frame.sample_rate == STT_RATE and frame.num_channels == 1:
        return bytes(frame.data)
    resampler = rtc.AudioResampler(frame.sample_rate, STT_RATE, num_channels=frame.num_channels)
    frames = resampler.push(frame) + resampler.flush()
    audio = rtc.combine_audio_frames(frames)
    if audio.num_channels == 1:
        return bytes(audio.data)
    # SpeechKit принимает только моно — берём первый канал
    samples = audio.data
    return samples[:: audio.num_channels].tobytes()


def raise_for(response: httpx.Response) -> None:
    if response.status_code != 200:
        raise APIStatusError(
            "SpeechKit refused the request",
            status_code=response.status_code,
            body=response.text[:300],
            retryable=response.status_code >= 500,
        )


def streaming_options(pause_ms: int) -> stt_pb2.StreamingOptions:
    return stt_pb2.StreamingOptions(
        recognition_model=stt_pb2.RecognitionModelOptions(
            model="general",
            audio_format=stt_pb2.AudioFormatOptions(
                raw_audio=stt_pb2.RawAudio(
                    audio_encoding=stt_pb2.RawAudio.LINEAR16_PCM,
                    sample_rate_hertz=STT_RATE,
                    audio_channel_count=1,
                )
            ),
            language_restriction=stt_pb2.LanguageRestrictionOptions(
                restriction_type=stt_pb2.LanguageRestrictionOptions.WHITELIST,
                language_code=["ru-RU"],
            ),
            audio_processing_type=stt_pb2.RecognitionModelOptions.REAL_TIME,
        ),
        eou_classifier=stt_pb2.EouClassifierOptions(
            default_classifier=stt_pb2.DefaultEouClassifier(
                type=stt_pb2.DefaultEouClassifier.DEFAULT,
                max_pause_between_words_hint_ms=pause_ms,
            )
        ),
    )


class SpeechKitSTT(stt.STT):
    # в разговоре речь распознаётся потоком (gRPC v3), а целиком фразу умеет распознать REST v1
    def __init__(
        self,
        api_key: str,
        folder_id: str,
        pause_ms: int = PAUSE_MS,
        http: httpx.AsyncClient | None = None,
        stub: Any = None,
    ) -> None:
        super().__init__(capabilities=stt.STTCapabilities(streaming=True, interim_results=True))
        self.api_key = api_key
        self.folder_id = folder_id
        self.pause_ms = pause_ms
        self.http = http or httpx.AsyncClient()
        self.stub = stub

    @property
    def provider(self) -> str:
        return "yandex"

    def recognizer(self) -> Any:
        if self.stub is None:
            channel = grpc.aio.secure_channel(STT_HOST, grpc.ssl_channel_credentials())
            self.stub = RecognizerStub(channel)
        return self.stub

    def stream(
        self,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> "SpeechKitRecognizeStream":
        return SpeechKitRecognizeStream(stt=self, conn_options=conn_options)

    async def _recognize_impl(
        self,
        buffer: utils.AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        try:
            response = await self.http.post(
                STT_URL,
                headers={"Authorization": f"Api-Key {self.api_key}"},
                params={
                    "folderId": self.folder_id,
                    "lang": "ru-RU",
                    "format": "lpcm",
                    "sampleRateHertz": STT_RATE,
                },
                content=to_mono_16k(buffer),
                timeout=conn_options.timeout,
            )
        except httpx.TimeoutException as error:
            raise APITimeoutError() from error
        except httpx.HTTPError as error:
            raise APIConnectionError() from error
        raise_for(response)

        text = response.json().get("result", "")
        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(language="ru", text=text)],
        )


class SpeechKitRecognizeStream(stt.RecognizeStream):
    def __init__(self, *, stt: SpeechKitSTT, conn_options: APIConnectOptions) -> None:
        super().__init__(stt=stt, conn_options=conn_options, sample_rate=STT_RATE)
        self.speechkit = stt
        self.speaking = False
        self.input_done = False

    async def _run(self) -> None:
        while not self.input_done:
            started = time.monotonic()
            try:
                await self.session()
            except grpc.aio.AioRpcError as error:
                if time.monotonic() - started < STABLE_SECONDS:
                    raise APIConnectionError(f"SpeechKit streaming failed: {error.code().name}") from error
                logger.warning("speech stream dropped after %.0f s, reconnecting", time.monotonic() - started)

    async def session(self) -> None:
        metadata = (
            ("authorization", f"Api-Key {self.speechkit.api_key}"),
            ("x-folder-id", self.speechkit.folder_id),
        )
        call = self.speechkit.recognizer().RecognizeStreaming(metadata=metadata)
        await call.write(stt_pb2.StreamingRequest(session_options=streaming_options(self.speechkit.pause_ms)))
        sender = asyncio.create_task(self.send(call))
        try:
            async for response in call:
                self.handle(response)
        finally:
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)

    async def send(self, call: Any) -> None:
        async for item in self._input_ch:
            if isinstance(item, rtc.AudioFrame):
                await call.write(stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=mono(item))))
        self.input_done = True
        await call.done_writing()

    def handle(self, response: stt_pb2.StreamingResponse) -> None:
        kind = response.WhichOneof("Event")
        if kind == "partial":
            text = best_text(response.partial)
            if text:
                self.start_speech()
                self.emit(stt.SpeechEventType.INTERIM_TRANSCRIPT, text)
        elif kind == "final":
            text = best_text(response.final)
            if text:
                self.start_speech()
                self.emit(stt.SpeechEventType.FINAL_TRANSCRIPT, text)
            if self.speaking:
                self.speaking = False
                self._event_ch.send_nowait(stt.SpeechEvent(type=stt.SpeechEventType.END_OF_SPEECH))

    def start_speech(self) -> None:
        if not self.speaking:
            self.speaking = True
            self._event_ch.send_nowait(stt.SpeechEvent(type=stt.SpeechEventType.START_OF_SPEECH))

    def emit(self, kind: stt.SpeechEventType, text: str) -> None:
        self._event_ch.send_nowait(
            stt.SpeechEvent(type=kind, alternatives=[stt.SpeechData(language="ru", text=text)])
        )


def best_text(update: stt_pb2.AlternativeUpdate) -> str:
    return update.alternatives[0].text.strip() if update.alternatives else ""


def mono(frame: rtc.AudioFrame) -> bytes:
    if frame.num_channels == 1:
        return bytes(frame.data)
    return frame.data[:: frame.num_channels].tobytes()


class SpeechKitTTS(tts.TTS):
    def __init__(
        self,
        api_key: str,
        folder_id: str,
        voice: str = "dasha",
        http: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=TTS_RATE,
            num_channels=1,
        )
        self.api_key = api_key
        self.folder_id = folder_id
        self.voice = voice
        self.http = http or httpx.AsyncClient()

    @property
    def provider(self) -> str:
        return "yandex"

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> "SpeechKitStream":
        return SpeechKitStream(tts=self, input_text=text, conn_options=conn_options)


class SpeechKitStream(tts.ChunkedStream):
    def __init__(self, *, tts: SpeechKitTTS, input_text: str, conn_options: APIConnectOptions) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self.speechkit = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        body = {
            "text": self.input_text,
            "hints": [{"voice": self.speechkit.voice}],
            "outputAudioSpec": {"rawAudio": {"audioEncoding": "LINEAR16_PCM", "sampleRateHertz": TTS_RATE}},
        }
        headers = {
            "Authorization": f"Api-Key {self.speechkit.api_key}",
            "x-folder-id": self.speechkit.folder_id,
        }
        output_emitter.initialize(
            request_id=utils.shortuuid(),
            sample_rate=TTS_RATE,
            num_channels=1,
            mime_type="audio/pcm",
        )
        try:
            # таймаут httpx считается на каждое чтение, а повисший ответ может тянуться бесконечно
            async with (
                asyncio.timeout(self._conn_options.timeout),
                self.speechkit.http.stream(
                    "POST", TTS_URL, headers=headers, json=body, timeout=self._conn_options.timeout
                ) as response,
            ):
                if response.status_code != 200:
                    await response.aread()
                raise_for(response)
                # ответ — строки JSON, в каждой кусок звука в base64
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line).get("result", {}).get("audioChunk", {}).get("data")
                    if chunk:
                        output_emitter.push(base64.b64decode(chunk))
        except (httpx.TimeoutException, TimeoutError) as error:
            raise APITimeoutError() from error
        except httpx.HTTPError as error:
            raise APIConnectionError() from error
        output_emitter.flush()

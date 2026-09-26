import asyncio

import grpc
import pytest
from livekit import rtc
from livekit.agents import APIConnectionError, APIConnectOptions, stt
from yandex.cloud.ai.stt.v3 import stt_pb2

from digital_employee import speechkit
from digital_employee.speechkit import SpeechKitSTT


def update(text):
    return stt_pb2.AlternativeUpdate(alternatives=[stt_pb2.Alternative(text=text)] if text else [])


def partial(text):
    return stt_pb2.StreamingResponse(partial=update(text))


def final(text):
    return stt_pb2.StreamingResponse(final=update(text))


class FakeCall:
    # отвечает заготовленными событиями и держит поток, пока агент не закончит слать звук
    def __init__(self, responses, error=None):
        self.responses = responses
        self.error = error
        self.writes = []
        self.finished = asyncio.Event()

    async def write(self, request):
        self.writes.append(request)

    async def done_writing(self):
        self.finished.set()

    def __aiter__(self):
        return self.read()

    async def read(self):
        for response in self.responses:
            yield response
        if self.error is not None:
            raise self.error
        await self.finished.wait()


class FakeRecognizer:
    def __init__(self, *calls):
        self.calls = list(calls)
        self.made = []

    def RecognizeStreaming(self, metadata):  # noqa: N802 — так называется метод в заглушке SpeechKit
        call = self.calls.pop(0)
        call.metadata = dict(metadata)
        self.made.append(call)
        return call


def frame(rate=48000, seconds=0.1):
    samples = int(rate * seconds)
    return rtc.AudioFrame(b"\x01\x00" * samples, rate, 1, samples)


async def events_of(stream, frames=3):
    for _ in range(frames):
        stream.push_frame(frame())
    stream.end_input()
    return [event async for event in stream]


def rpc_error():
    return grpc.aio.AioRpcError(grpc.StatusCode.UNAVAILABLE, grpc.aio.Metadata(), grpc.aio.Metadata())


async def test_speech_turns_into_start_interim_final_and_end():
    call = FakeCall([partial("какую"), partial("какую категорию"), final("какую категорию выбрать")])
    recognizer = SpeechKitSTT("secret", "folder", pause_ms=800, stub=FakeRecognizer(call))

    events = await events_of(recognizer.stream())

    assert [event.type for event in events] == [
        stt.SpeechEventType.START_OF_SPEECH,
        stt.SpeechEventType.INTERIM_TRANSCRIPT,
        stt.SpeechEventType.INTERIM_TRANSCRIPT,
        stt.SpeechEventType.FINAL_TRANSCRIPT,
        stt.SpeechEventType.END_OF_SPEECH,
    ]
    assert events[3].alternatives[0].text == "какую категорию выбрать"


async def test_stream_is_opened_with_our_options_and_16k_audio():
    call = FakeCall([])
    recognizer = SpeechKitSTT("secret", "folder", pause_ms=800, stub=FakeRecognizer(call))

    await events_of(recognizer.stream(), frames=2)
    options = call.writes[0].session_options
    chunks = [request.chunk.data for request in call.writes[1:]]

    assert call.metadata == {"authorization": "Api-Key secret", "x-folder-id": "folder"}
    assert options.eou_classifier.default_classifier.max_pause_between_words_hint_ms == 800
    assert options.recognition_model.audio_format.raw_audio.sample_rate_hertz == 16000
    assert list(options.recognition_model.language_restriction.language_code) == ["ru-RU"]
    # 0,2 с звука в 16 кГц, 16 бит — около 6400 байт, сколько бы ни было на входе
    assert 6000 <= sum(len(chunk) for chunk in chunks) <= 6400


async def test_noise_without_words_is_not_a_phrase():
    call = FakeCall([partial(""), final("")])
    recognizer = SpeechKitSTT("secret", "folder", stub=FakeRecognizer(call))

    assert await events_of(recognizer.stream()) == []


async def test_failure_right_away_is_an_api_error():
    call = FakeCall([], error=rpc_error())
    recognizer = SpeechKitSTT("secret", "folder", stub=FakeRecognizer(call))

    with pytest.raises(APIConnectionError):
        await events_of(recognizer.stream(conn_options=APIConnectOptions(max_retry=0)))


async def test_long_stream_that_dropped_is_opened_again(monkeypatch):
    # у SpeechKit есть предел длины потока: встреча не должна из-за него оглохнуть
    monkeypatch.setattr(speechkit, "STABLE_SECONDS", -1)
    dropped = FakeCall([partial("я")], error=rpc_error())
    fresh = FakeCall([final("какую категорию выбрать")])
    stub = FakeRecognizer(dropped, fresh)
    recognizer = SpeechKitSTT("secret", "folder", stub=stub)

    events = await events_of(recognizer.stream())

    assert len(stub.made) == 2
    assert stt.SpeechEventType.FINAL_TRANSCRIPT in [event.type for event in events]

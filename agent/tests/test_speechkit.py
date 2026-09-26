import base64
import json

import httpx
import pytest
from livekit import rtc
from livekit.agents import APIConnectionError, APIConnectOptions, APIStatusError

from digital_employee.speechkit import SpeechKitSTT, SpeechKitTTS


def frame(rate=48000, seconds=0.5):
    samples = int(rate * seconds)
    return rtc.AudioFrame(b"\x01\x00" * samples, rate, 1, samples)


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_speech_is_sent_as_16k_mono_and_text_comes_back():
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        seen["size"] = len(request.content)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json={"result": "какую категорию выбрать"})

    stt = SpeechKitSTT("secret", "folder", http=client(handler))
    event = await stt.recognize([frame()])

    assert event.alternatives[0].text == "какую категорию выбрать"
    assert seen["params"]["sampleRateHertz"] == "16000"
    assert seen["params"]["lang"] == "ru-RU"
    assert seen["params"]["folderId"] == "folder"
    assert seen["auth"] == "Api-Key secret"
    # полсекунды звука в 16 кГц, 16 бит — около 16 000 байт
    assert 15000 < seen["size"] < 17000


async def test_refusal_of_recognition_is_an_api_error():
    stt = SpeechKitSTT("secret", "folder", http=client(lambda _: httpx.Response(401, text="bad key")))

    with pytest.raises((APIStatusError, APIConnectionError)):
        await stt.recognize([frame(16000)], conn_options=APIConnectOptions(max_retry=0))


async def test_synthesis_collects_audio_chunks():
    seen = {}
    chunk = base64.b64encode(b"\x00\x00" * 4800).decode()

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["folder"] = request.headers["x-folder-id"]
        lines = [json.dumps({"result": {"audioChunk": {"data": chunk}}})] * 2
        return httpx.Response(200, text="\n".join(lines))

    tts = SpeechKitTTS("secret", "folder", voice="dasha", http=client(handler))
    frames = [item.frame async for item in tts.synthesize("Здравствуйте!")]

    assert seen["body"]["text"] == "Здравствуйте!"
    assert seen["body"]["hints"] == [{"voice": "dasha"}]
    assert seen["folder"] == "folder"
    # последний кадр фреймворк добивает тишиной до своей длины
    assert 9600 <= sum(item.samples_per_channel for item in frames) < 9600 + 4800


async def test_refusal_of_synthesis_is_an_api_error():
    tts = SpeechKitTTS("secret", "folder", http=client(lambda _: httpx.Response(400, text="bad voice")))

    with pytest.raises((APIStatusError, APIConnectionError)):
        async for _ in tts.synthesize("Здравствуйте!", conn_options=APIConnectOptions(max_retry=0)):
            pass

# Цифровой сотрудник

Голосовой агент для встречи помощи: слышит вопрос владельца, отвечает голосом и подсвечивает поля. Как он устроен и почему так — в 12.

Агент — отдельный процесс на LiveKit Agents. Он регистрируется в LiveKit как `digital-employee` и ждёт, пока backend позовёт его во встречу. Дальше он заходит в комнату LiveKit и в WebSocket встречи со своим токеном — как обычный участник с ролью `ai_agent`.

## Запуск в докере

Из корня репозитория, после `api` и `livekit`:

```bash
docker compose up -d --build agent
```

Ключ Yandex AI Studio берётся из `YANDEX_API_KEY` и `YANDEX_FOLDER_ID` — так же, как для `api`. В логе должна появиться строка `registered worker` с `"agent_name": "digital-employee"`:

```bash
docker compose logs --tail=20 agent
```

## Запуск из PyCharm или терминала

Нужен Python 3.12 — тот же, что в образе.

```bash
py -3.12 -m venv .venv
```

```bash
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Переменные окружения: `LIVEKIT_URL=ws://localhost:7880`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `BACKEND_URL=http://localhost:8000`, `YANDEX_API_KEY`, `YANDEX_FOLDER_ID`. Остальное имеет значения по умолчанию — см. `digital_employee/config.py`.

```bash
.venv\Scripts\python.exe -m digital_employee start
```

Одновременно должен работать только один агент — либо в докере, либо локально. Иначе LiveKit будет раздавать встречи обоим.

## Настройки

| Переменная | По умолчанию | Что это |
|---|---|---|
| `AGENT_NAME` | `digital-employee` | под этим именем backend вызывает агента |
| `BACKEND_URL` | `http://localhost:8000` | адрес API; WebSocket — тот же адрес со схемой `ws` |
| `AI_LLM_MODEL` | `qwen3-235b-a22b-fp8/latest` | модель в каталоге Yandex AI Studio |
| `AI_VOICE` | `dasha` | голос SpeechKit, только из API v3 |
| `AI_SILENCE_SECONDS` | `1.0` | пауза, после которой фраза считается законченной |

## Тесты

```bash
.venv\Scripts\python.exe -m pytest
```

Тесты не ходят в сеть: Яндекс и backend подменяются.

В лог агент пишет, за сколько ответил и сколько ушло на распознавание, модель и синтез. Текст речи человека в наш лог не попадает.

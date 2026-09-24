# Backend — «Рядом»

## Запуск

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

```bash
copy .env.example .env
```

```bash
docker compose -f ..\docker-compose.yml up -d postgres
```

```bash
.venv\Scripts\python.exe -m alembic upgrade head
```

```bash
.venv\Scripts\python.exe -m uvicorn max_assist.main:app --reload --app-dir src
```

Для Linux и macOS вместо `.venv\Scripts\python.exe` — `.venv/bin/python`, вместо `copy` — `cp`.

`requirements.txt` — то, что нужно для работы сервиса. `requirements-dev.txt` включает его и добавляет pytest и ruff. Пакет не устанавливается в окружение: исходники подключаются через `--app-dir src` (сервер), `prepend_sys_path` в `alembic.ini` (миграции) и `pythonpath` в `pyproject.toml` (тесты).

Или одной командой, вместе с миграциями — в PyCharm достаточно нажать Run на `run.py`:

```bash
.venv\Scripts\python.exe run.py
```

Swagger: http://localhost:8000/docs

Postgres из compose слушает порт 5433, чтобы не конфликтовать с локально установленным Postgres на 5432.

## Запуск целиком в докере

`docker-compose.yml` лежит в корне репозитория — он общий для бэкенда и фронтенда. Из корня:

```bash
docker compose up --build
```

Поднимется база и API на http://localhost:8000. Миграции применяются при старте контейнера, демо-услуга приходит вместе с ними — отдельных команд не нужно. Образ описан в [Dockerfile](Dockerfile), исходники внутрь копируются, поэтому после правок нужен `--build`.

Для повседневной разработки удобнее локальный `run.py`, а докер — чтобы проверить сборку целиком и отдать проект жюри.

## Вход без MAX

Пока нет токена бота, вход через dev-режим (`APP_ENV=dev`):

```bash
curl -X POST localhost:8000/api/v1/auth/dev-login -H 'content-type: application/json' -d '{"user_key": "ludmila"}'
```

Список доступных ключей — `GET /api/v1/dev/users`. Пользователь создаётся при первом входе.

## Тесты

```bash
.venv\Scripts\python.exe -m pytest
```

С покрытием:

```bash
.venv\Scripts\python.exe -m pytest --cov=max_assist --cov-report=term-missing
```

Тесты работают с той же базой, что указана в `.env`, и сами убирают за собой через `POST /dev/reset`. Отдельная тестовая база не нужна, но и не мешает — достаточно поменять `DATABASE_URL`.

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

Если порт 8000 или 5433 уже занят другим проектом, задайте свои через `API_PORT` и `POSTGRES_PORT`. В PowerShell:

```powershell
$env:API_PORT = "8001"; docker compose up -d --build
```

В bash:

```bash
API_PORT=8001 docker compose up -d --build
```

При частых пересборках Docker копит старые образы и кеш сборки — это отдельно от базы и лимитами compose не ограничивается. Освободить место:

```bash
docker image prune
```

```bash
docker builder prune
```

## Соединения с базой

Что не даёт соединениям копиться:

- Пул приложения: до 15 соединений на процесс. Если пул исчерпан, запрос ждёт не больше 10 секунд и падает с ошибкой, а не висит. Соединения старше 5 минут пересоздаются.
- Каждое соединение помечено `application_name = ryadom-api`. Postgres сам обрывает запрос дольше 30 секунд, транзакцию, оставленную открытой дольше минуты, и простаивающее соединение дольше 10 минут.
- При остановке приложение дожидается фоновых задач и закрывает пул. В контейнере uvicorn запускается через `exec` и сам получает сигнал остановки — иначе Docker убил бы процесс, не дав закрыть соединения.
- В docker-compose Postgres принимает не больше 50 соединений и раз в минуту проверяет, жив ли клиент: соединения упавшего приложения закрываются примерно через 2 минуты, а не через 2 часа. Логи контейнеров ротируются (3 файла по 10 МБ), у контейнеров лимиты памяти и процессора: база — 1 ядро и 1 ГБ, приложение — 1 ядро и 512 МБ.
- Тесты проверяют, что после каждого теста в пуле не осталось занятых соединений.

Кто сейчас держит соединения:

```bash
psql -h localhost -U postgres -d assist -c "select application_name, state, count(*) from pg_stat_activity where datname = 'assist' group by 1, 2 order by 3 desc"
```

Нормальная картина — несколько строк `ryadom-api | idle`. Подозрительно — растущее со временем число строк или `idle in transaction`.

## Рост базы

Приложение раз в час удаляет устаревшие данные (первый раз — сразу при старте). Сроки настраиваются в `.env`:

| Что удаляется | Через сколько | Переменная |
|---|---|---|
| Демо-SMS с кодами | 24 часа | `RETENTION_INBOX_HOURS` |
| Ссылки-приглашения | 7 дней | `RETENTION_INVITES_DAYS` |
| Брошенные черновики и отменённые заявления (вместе с их сессиями помощи) | 30 дней без изменений | `RETENTION_DRAFTS_DAYS` |
| Завершённые сессии помощи | 90 дней | `RETENTION_ASSIST_DAYS` |
| Отправленные заявления | 90 дней | `RETENTION_SUBMITTED_DAYS` |

Если очистка упала (например, база была недоступна), ошибка пишется в лог, а следующая попытка будет по расписанию. Отключить очистку — `CLEANUP_ENABLED=false`.

Postgres в docker-compose дополнительно ограничен: журнал транзакций (WAL) — до 512 МБ, временные файлы одного запроса — до 256 МБ; autovacuum запускается чаще стандартного, чтобы обновляемые черновики не раздували таблицы.

Размер базы виден в `GET /health` (`db_size_mb`). Если он больше `DB_SIZE_WARNING_MB` (по умолчанию 1024), статус становится `degraded`, а в лог при каждой очистке пишется предупреждение.

Жёсткого лимита на размер тома Docker не даёт. Если на сервере нужна гарантия, что база не займёт весь диск, храните том на отдельном разделе фиксированного размера.

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

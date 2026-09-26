# «Рядом» — MAX mini app

Mini app для совместного прохождения госуслуг с голосовой помощью, безопасной проекцией формы и указателем помощника.

Основной production URL: `https://max-hackathon.explainlaw.ru`.
Официальный бот: `https://max.ru/t562_hakaton_max_bot`.

## Локальный запуск

Backend и инфраструктура:

```bash
docker compose up -d --build
curl -fsS http://localhost:8000/health
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Локальный frontend использует `http://localhost:8000/api/v1`, а dev-вход — `POST /api/v1/auth/dev-login`. MAX Bridge в обычном браузере недоступен, поэтому используется экран `D1`.

Проверка frontend:

```bash
cd frontend
npm run build
npm run lint
```

Проверка backend:

```bash
cd backend
python -m pytest
python -m ruff check src tests
```

Проверка Compose:

```bash
docker compose config --quiet
```

## Production-проверка

На VM:

```bash
docker compose up -d --build
docker compose ps
curl -fsS https://max-hackathon.explainlaw.ru/health
curl -fsS https://max-hackathon.explainlaw.ru/api/v1/services
sudo nginx -t
sudo certbot renew --dry-run
```

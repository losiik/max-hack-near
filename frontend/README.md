# Frontend — «Рядом»

React + TypeScript + Vite frontend для MAX mini app.

Визуальная основа — официальный [`@maxhub/max-ui`](https://dev.max.ru/ui), интеграция с MAX — [MAX Bridge](https://dev.max.ru/docs/webapps/bridge).

## Запуск

```bash
npm ci
npm run dev
```

Локально frontend доступен на `http://localhost:5173`. Vite proxy отправляет `/api`, `/health`, `/openapi.json` и `/ws` в backend на `http://localhost:8000`.

## Проверка

```bash
npm run lint
npm run build
```

В MAX runtime авторизация использует `window.WebApp.initData`. В обычном браузере открывается `D1` с dev-пользователями.

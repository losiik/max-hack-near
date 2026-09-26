SHELL := /bin/bash

VM ?=
DOMAIN ?=
APP_DIR ?= /opt/max-hackathon
WEB_ROOT ?= /var/www/max-hackathon

LOCAL_WEB_PORT ?= 3000
LOCAL_WEB_BIND_ADDRESS ?= 127.0.0.1
LOCAL_CHECK_HOST ?= 127.0.0.1
LOCAL_LIVEKIT_NODE_IP ?= 127.0.0.1
LOCAL_COMPOSE_ENV = APP_ENV=dev POSTGRES_USER=assist POSTGRES_PASSWORD=assist POSTGRES_DB=assist DATABASE_URL=postgresql+asyncpg://assist:assist@postgres:5432/assist JWT_SECRET=dev-secret-change-me-32-bytes-minimum FIELD_ENCRYPTION_KEY=MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY= POSTGRES_BIND_ADDRESS=127.0.0.1 POSTGRES_PORT=5433 API_BIND_ADDRESS=127.0.0.1 API_PORT=8000 CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000 LIVEKIT_URL=ws://localhost:7880 LIVEKIT_API_URL=http://livekit:7880 LIVEKIT_API_KEY=devkey LIVEKIT_API_SECRET=dev-livekit-secret-change-me-32-bytes LIVEKIT_BIND_ADDRESS=127.0.0.1 LIVEKIT_CONFIG_FILE=./livekit/livekit.yaml LIVEKIT_EGRESS_CONFIG_FILE=./livekit/egress.yaml LIVEKIT_NODE_IP=$(LOCAL_LIVEKIT_NODE_IP) MAX_BOT_TOKEN= REVIEW_LOGIN=review REVIEW_PASSWORD= YANDEX_API_KEY= YANDEX_FOLDER_ID= AI_LLM_MODEL=qwen3-235b-a22b-fp8/latest AI_VOICE=dasha FRONTEND_BUILD_MODE=development RECORDINGS_VOLUME=local_recordings EGRESS_USER=0:0

.PHONY: check build deploy deploy-frontend deploy-backend deploy-local local-down local-clean local-logs production-check remote-env

remote-env:
	@test -n "$(VM)" || { echo "Укажите сервер: make $(MAKECMDGOALS) VM=user@host DOMAIN=example.ru" >&2; exit 1; }
	@test -n "$(DOMAIN)" || { echo "Укажите домен: make $(MAKECMDGOALS) VM=user@host DOMAIN=example.ru" >&2; exit 1; }

check:
	cd frontend && npm run lint && npm run build

build:
	cd frontend && npm run build

deploy-frontend: remote-env
	VM="$(VM)" DOMAIN="$(DOMAIN)" bash scripts/deploy-production.sh frontend

deploy-backend: remote-env
	VM="$(VM)" DOMAIN="$(DOMAIN)" bash scripts/deploy-production.sh backend

deploy: remote-env
	VM="$(VM)" DOMAIN="$(DOMAIN)" bash scripts/deploy-production.sh all

deploy-local:
	$(LOCAL_COMPOSE_ENV) WEB_PORT=$(LOCAL_WEB_PORT) WEB_BIND_ADDRESS=$(LOCAL_WEB_BIND_ADDRESS) docker compose --profile local up -d --build
	@for attempt in $$(seq 1 30); do \
		if curl -fsS http://$(LOCAL_CHECK_HOST):$(LOCAL_WEB_PORT)/health; then exit 0; fi; \
		sleep 2; \
	done; \
	echo "Local API did not become healthy" >&2; \
	docker compose --profile local ps; \
	exit 1
	docker compose --profile local ps

local-down:
	$(LOCAL_COMPOSE_ENV) docker compose --profile local down

# Удаляет контейнеры, сеть, локальные образы и данные (Postgres + записи) этого Compose-проекта.
local-clean:
	$(LOCAL_COMPOSE_ENV) docker compose --profile local down --volumes --rmi local --remove-orphans

local-logs:
	$(LOCAL_COMPOSE_ENV) docker compose --profile local logs -f nginx frontend api postgres redis livekit egress agent

production-check: remote-env
	ssh $(VM) 'set -eu; curl -fsS https://$(DOMAIN)/health; echo; cd $(APP_DIR); docker compose ps --format "table {{.Service}}\\t{{.State}}"'

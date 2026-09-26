SHELL := /bin/bash

VM ?=
DOMAIN ?=
APP_DIR ?= /opt/max-hackathon
WEB_ROOT ?= /var/www/max-hackathon

.PHONY: check build deploy deploy-frontend deploy-backend production-check remote-env

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

production-check: remote-env
	ssh $(VM) 'set -eu; curl -fsS https://$(DOMAIN)/health; echo; cd $(APP_DIR); docker compose ps --format "table {{.Service}}\\t{{.State}}"'

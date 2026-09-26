#!/usr/bin/env bash
set -euo pipefail

scope="${1:-all}"
case "$scope" in
  frontend|backend|all) ;;
  *) echo "Usage: $0 frontend|backend|all" >&2; exit 2 ;;
esac

repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"

if [[ "${ALLOW_DIRTY:-0}" != 1 ]]; then
  if ! git diff --quiet || ! git diff --cached --quiet || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
    echo "Рабочее дерево не чистое. Сначала закоммитьте изменения или используйте ALLOW_DIRTY=1 осознанно." >&2
    git status --short >&2
    exit 1
  fi
fi

vm="${VM:?Укажите сервер: VM=user@host}"
domain="${DOMAIN:?Укажите домен: DOMAIN=example.ru}"
app_dir="${APP_DIR:-/opt/max-hackathon}"
web_root="${WEB_ROOT:-/var/www/max-hackathon}"
release="${DEPLOY_ID:-$(git rev-parse --short HEAD)-$(date -u +%Y%m%dT%H%M%SZ)}"

if [[ "$scope" == frontend || "$scope" == all ]]; then
  (cd frontend && npm run lint && npm run build)
  stage="${web_root}-stage-${release}"
  ssh "$vm" "mkdir -p '$stage'"
  rsync -az --delete frontend/dist/ "$vm:$stage/"
  ssh "$vm" "set -eu
    test -f '$stage/index.html'
    test -d '$stage/assets'
    mkdir -p /var/backups/max-hackathon
    cp -a '$web_root' '/var/backups/max-hackathon/frontend-$release'
    mv '$web_root' '${web_root}-previous-$release'
    mv '$stage' '$web_root'"
  echo "frontend deployed: $release"
fi

if [[ "$scope" == backend || "$scope" == all ]]; then
  ssh "$vm" "set -eu
    cd '$app_dir'
    backup='/var/backups/max-hackathon/release-$release'
    mkdir -p \"\$backup\"
    cp -a docker-compose.yml backend livekit scripts deploy .env \"\$backup/\""

  rsync -az --delete \
    --exclude='.git/' \
    --exclude='**/.env' \
    --exclude='recordings/' \
    --exclude='frontend/node_modules/' \
    --exclude='frontend/dist/' \
    --exclude='livekit/*.production.yaml' \
    ./ "$vm:$app_dir/"

  ssh "$vm" "set -eu
    cd '$app_dir'
    if ! grep -q '^LIVEKIT_EGRESS_CONFIG_FILE=' .env; then
      printf '\\nLIVEKIT_EGRESS_CONFIG_FILE=./livekit/egress.production.yaml\\n' >> .env
    fi
    sh scripts/render-livekit-production.sh
    chown root:root recordings
    chmod 0770 recordings
    docker compose config >/dev/null
    docker compose up -d --build api agent
    docker compose up -d egress"
  echo "backend deployed: $release"
fi

ssh "$vm" "curl -fsS https://$domain/health >/dev/null"
echo "production health: ok"

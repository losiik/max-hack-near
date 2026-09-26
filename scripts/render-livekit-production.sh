#!/bin/sh
set -eu

if [ ! -f .env ]; then
  echo "Production .env is required in the repository root." >&2
  exit 1
fi

set -a
. ./.env
set +a

: "${LIVEKIT_API_KEY:?LIVEKIT_API_KEY is required}"
: "${LIVEKIT_API_SECRET:?LIVEKIT_API_SECRET is required}"

livekit_template=deploy/livekit/livekit.production.template.yaml
livekit_output=livekit/livekit.production.yaml
egress_template=deploy/livekit/egress.production.template.yaml
egress_output=livekit/egress.production.yaml

umask 077
sed "s/__LIVEKIT_API_KEY__/${LIVEKIT_API_KEY}/g" "$livekit_template" >"$livekit_output"
sed -e "s/__LIVEKIT_API_KEY__/${LIVEKIT_API_KEY}/g" -e "s/__LIVEKIT_API_SECRET__/${LIVEKIT_API_SECRET}/g" "$egress_template" >"$egress_output"
chmod 600 "$livekit_output"
# Egress runs as a non-root user in the root group inside its container.
# Keep the secret unreadable to other VM users.
chmod 640 "$egress_output"

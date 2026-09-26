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

template=deploy/livekit/livekit.production.template.yaml
output=livekit/livekit.production.yaml

umask 077
sed "s/__LIVEKIT_API_KEY__/${LIVEKIT_API_KEY}/g" "$template" >"$output"
chmod 600 "$output"

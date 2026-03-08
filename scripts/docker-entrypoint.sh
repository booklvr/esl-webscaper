#!/usr/bin/env sh
set -eu

HOST="${DASHBOARD_HOST:-0.0.0.0}"
PORT="${DASHBOARD_PORT:-8080}"

mkdir -p /app/data

if [ "${RUN_TESTS_ON_START:-0}" = "1" ]; then
  python -m unittest discover -s tests -v
fi

exec python -m dashboard.server --host "$HOST" --port "$PORT"

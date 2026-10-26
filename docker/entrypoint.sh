#!/bin/sh
# Aplica as migrations e, se SEED_DEMO=true, carrega os dados fictícios (idempotente).
set -e
alembic upgrade head
if [ "${SEED_DEMO:-false}" = "true" ]; then
  python /app/scripts/seed_demo_data.py
fi
exec "$@"

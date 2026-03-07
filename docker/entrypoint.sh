#!/bin/bash
set -euo pipefail

# Activate virtual environment
. /opt/venv/bin/activate

# Wait for database connection with timeout
echo "Waiting for database..."
max_attempts=60
attempt=1
DB_HOST="${DB_HOST:-}"
DB_PORT="${DB_PORT:-}"

if [ -z "$DB_HOST" ] || [ -z "$DB_PORT" ]; then
  db_target=$(python - <<'PY'
import os
from urllib.parse import urlparse

parsed = urlparse(os.environ.get("DATABASE_URL", ""))
host = parsed.hostname or "localhost"
port = parsed.port or 5432
print(f"{host}:{port}")
PY
)
  DB_HOST="${DB_HOST:-${db_target%:*}}"
  DB_PORT="${DB_PORT:-${db_target##*:}}"
fi

while ! nc -z "$DB_HOST" "$DB_PORT"; do
  if [ $attempt -ge $max_attempts ]; then
    echo "ERROR: Database not available after $max_attempts seconds"
    exit 1
  fi
  echo "  Attempt $attempt/$max_attempts..."
  sleep 1
  attempt=$((attempt + 1))
done
echo "Database is ready."

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Start supervisord
echo "Starting application..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/mundaneum.conf

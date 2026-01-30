#!/bin/bash
set -euo pipefail

# Activate virtual environment
. /opt/venv/bin/activate

# Wait for database connection with timeout
echo "Waiting for database..."
max_attempts=60
attempt=1
while ! nc -z ${DB_HOST:-folio-db} ${DB_PORT:-5432}; do
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
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/folio.conf

# Mundaneum

Monorepo for the Mundaneum app.

- `frontend/`: Vue 3 + Vite SPA
- `backend/`: FastAPI + SQLAlchemy + Alembic
- `docker-compose.yml`: development services
- `scripts/docker.sh`: local clean-start helper
- `Dockerfile`: combined runtime image

## Local Dev

Backend:

```bash
cd backend
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Default dev URLs:

- frontend: `http://localhost:5173`
- backend: `http://localhost:8000`
- API docs: `http://localhost:8000/api/docs`

## Docker Helper

Build and start:

```bash
./scripts/docker.sh sync-bibliography
./scripts/docker.sh build
./scripts/docker.sh start
```

Current helper defaults:

- app: `http://localhost:8080`
- postgres: `localhost:15432`
- meilisearch: `http://localhost:17700`

Useful env vars:

- `MUNDANEUM_PORT`
- `DB_PORT`
- `MEILI_PORT`
- `POSTGRES_PASSWORD`
- `BIBLIOGRAPHY_REPO_URL`
- `BIBLIOGRAPHY_CHECKOUT_PATH`
- `BIBLIOGRAPHY_REPO_REF`
- `BIBLIOGRAPHY_HOST_CACHE`
- `BIBLIOGRAPHY_SYNC_TIMEOUT_SECONDS`
- `BIBLIOGRAPHY_RUNTIME_SYNC_ENABLED`
- `DOCS_DIRECTORY`
- `S2_DATA_DIR`

Clean reset:

```bash
./scripts/docker.sh clean
```

## Docker Compose

If `docker compose` is available:

```bash
cp .env.example .env
docker compose up -d
docker compose exec backend alembic upgrade head
```

## Common Checks

Backend tests:

```bash
cd backend
poetry run pytest
```

Frontend production build:

```bash
cd frontend
npm run build
```

Import BibTeX from the running backend:

```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{}'
```

By default Mundaneum syncs the bibliography from
`https://github.com/b-vitamins/bibliography/` into the configured local
checkout path before ingesting. The Docker helper does that sync on the host
and mounts the checked-out repo into the container, which avoids runtime DNS
issues inside Docker. You can still point `/api/ingest` at an explicit absolute
directory for one-off imports.

Health check:

```bash
curl http://localhost:8080/health
```

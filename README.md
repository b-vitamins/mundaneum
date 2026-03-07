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
- `BIB_DIRECTORY`
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
curl -X POST http://localhost:8000/api/import \
  -H "Content-Type: application/json" \
  -d '{"directory": "/path/to/bibtex"}'
```

Health check:

```bash
curl http://localhost:8080/health
```

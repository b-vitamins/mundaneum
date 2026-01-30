# Folio

A minimal, powerful interface for your personal library of books and papers.

![Folio Screenshot](docs/screenshot.png)

## Features

- **Full-text Search** — Powered by Meilisearch with instant results
- **Smart Filters** — Filter by type, year range, author, PDF availability
- **Collections** — Organize entries into custom reading lists
- **Dark Mode** — Toggle between paper white and charcoal themes
- **Keyboard First** — `/` to search, `g h` for home, `g c` for collections
- **BibTeX Native** — Import from `.bib` files, export citations

## Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/folio.git
cd folio

# Start all services
./scripts/docker.sh start

# Open in browser
open http://localhost:8080
```

This starts PostgreSQL, Meilisearch, and the Folio application.

### Using Docker Compose

If you have a working `docker-compose`:

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
vim .env

# Start services
docker compose up -d

# Run database migrations
docker compose exec backend alembic upgrade head
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://folio:folio@localhost:5432/folio` | PostgreSQL connection string |
| `MEILI_URL` | `http://localhost:7700` | Meilisearch URL |
| `MEILI_API_KEY` | (none) | Meilisearch API key (optional) |
| `BIB_DIRECTORY` | `/data` | Path to BibTeX files |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins (comma-separated) |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Docker Ports

The `scripts/docker.sh` uses non-standard ports to avoid conflicts:

| Service | Port |
|---------|------|
| Folio Web UI | 8080 |
| PostgreSQL | 15432 |
| Meilisearch | 17700 |

Override with environment variables:

```bash
FOLIO_PORT=3000 DB_PORT=5432 ./scripts/docker.sh start
```

## Importing BibTeX Files

### From Docker

Mount your BibTeX directory and trigger import:

```bash
# With docker.sh
BIB_DIRECTORY=/path/to/bibtex ./scripts/docker.sh start

# Then import via API
curl -X POST http://localhost:8080/api/import
```

### From Development

```bash
curl -X POST http://localhost:8000/api/import \
  -H "Content-Type: application/json" \
  -d '{"directory": "/path/to/bibtex"}'
```

## Development

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 14+
- Meilisearch 1.6+

### Backend Setup

```bash
cd backend

# Install dependencies
poetry install

# Start database and meilisearch (using docker)
docker compose up -d db search

# Run migrations
poetry run alembic upgrade head

# Start development server
poetry run uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend runs at http://localhost:5173 and proxies API requests to the backend.

### Running Tests

```bash
# Backend tests
cd backend
poetry run pytest

# Frontend build check
cd frontend
npm run build
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           Browser                                │
│                      (Vue 3 + Vite SPA)                         │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP
┌─────────────────────────────▼───────────────────────────────────┐
│                         Nginx                                    │
│              (Static files + API proxy)                          │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                    FastAPI Backend                               │
│          (Uvicorn + SQLAlchemy + Pydantic)                      │
└────────────┬────────────────────────────────────┬───────────────┘
             │                                    │
┌────────────▼────────────┐          ┌───────────▼───────────────┐
│      PostgreSQL         │          │       Meilisearch         │
│   (Primary data store)  │          │   (Full-text search)      │
└─────────────────────────┘          └───────────────────────────┘
```

### Project Structure

```
folio/
├── Dockerfile              # Combined image (frontend + backend)
├── docker-compose.yml      # Development services
├── scripts/
│   └── docker.sh           # Docker management script
├── docker/
│   ├── nginx.conf          # Production nginx config
│   └── supervisord.conf    # Process manager config
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI application
│   │   ├── config.py       # Settings with Pydantic
│   │   ├── models.py       # SQLAlchemy models
│   │   ├── routers/        # API endpoints
│   │   └── services/       # Business logic
│   └── alembic/            # Database migrations
└── frontend/
    └── src/
        ├── views/          # Page components
        ├── api/            # API client
        └── composables/    # Vue composables
```

## API Reference

### Health Check

```
GET /health
```

Returns service status:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "services": {
    "database": "ok",
    "search": "ok"
  }
}
```

### Statistics

```
GET /api/stats
```

Returns library counts:

```json
{
  "entries": 1234,
  "authors": 567,
  "collections": 8
}
```

### Search

```
GET /api/entries/search?q=quantum&entry_type=article&year_from=2020&limit=20
```

### Entry Details

```
GET /api/entries/{id}
```

### BibTeX Export

```
GET /api/entries/{id}/bibtex
```

Returns plain text BibTeX.

### Collections

```
GET    /api/collections           # List all
POST   /api/collections           # Create new
GET    /api/collections/{id}      # Get with entries
DELETE /api/collections/{id}      # Delete
POST   /api/collections/{id}/entries/{entry_id}    # Add entry
DELETE /api/collections/{id}/entries/{entry_id}    # Remove entry
```

## Deployment

### Production Docker

Build and run the single combined image:

```bash
# Build image
docker build -t folio .

# Run with external database
docker run -d \
  --name folio \
  -e DATABASE_URL=postgresql://user:pass@host:5432/folio \
  -e MEILI_URL=http://meilisearch:7700 \
  -v /path/to/bibtex:/data:ro \
  -p 80:80 \
  folio
```

### Guix System

If using Guix with Docker:

```bash
# Use docker-cli package (not podman)
guix shell docker-cli -- ./scripts/docker.sh start
```

### Manual Deployment

1. Install PostgreSQL 14+ and Meilisearch 1.6+
2. Create database and run migrations
3. Build frontend: `cd frontend && npm run build`
4. Serve frontend with nginx
5. Run backend with gunicorn/uvicorn

## Troubleshooting

### Search not working

Check Meilisearch is running:

```bash
curl http://localhost:7700/health
```

Re-index entries:

```bash
curl -X POST http://localhost:8000/api/import
```

### Database connection errors

Verify PostgreSQL is running and DATABASE_URL is correct:

```bash
psql $DATABASE_URL -c "SELECT 1"
```

### Docker build fails

On Guix, use `--network=host` for builds:

```bash
guix shell docker-cli -- docker build --network=host -t folio .
```

## License

MIT

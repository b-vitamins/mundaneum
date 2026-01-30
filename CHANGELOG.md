# Changelog

All notable changes to Folio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Semantic Scholar Integration**
  - "Citations" and "References" tabs for entries, displaying related papers.
  - Automatic background sync of citation data from Semantic Scholar API.
  - Efficient, parallel fetching of citation data.
  - Smart caching (staleness check) to respect API limits and improve performance.
  - Database index on citations for fast reverse lookups.

- **Search & UI**
  - Fixed "Recent" filter to correctly sort by latest entries.
  - Support for browsing entries without a search query.
  - Robust error handling for external API failures.

### Changed
- **Backend Optimization**
  - Refactored `S2Service` to use Pydantic models for strict type safety.
  - Improved logging for background tasks.

## [0.1.0] - 2026-01-30

### Added

- **Core Features**
  - Full-text search powered by Meilisearch
  - BibTeX import from directories
  - Entry detail view with metadata display
  - Collections for organizing entries
  - Notes per entry with auto-save
  - Read/unread status tracking
  - BibTeX export for individual entries

- **User Interface**
  - Vue 3 + Vite frontend
  - Dark mode with system preference detection
  - Keyboard shortcuts (`/` for search, `g h` for home)
  - Responsive design
  - Loading states and error handling

- **Backend**
  - FastAPI with async SQLAlchemy
  - PostgreSQL for primary data storage
  - Meilisearch for full-text search
  - Health check endpoint with service status
  - Structured logging
  - Graceful degradation when Meilisearch unavailable

- **Deployment**
  - Single combined Docker image
  - Docker management script for Guix compatibility
  - Docker Compose for development
  - Configurable ports and environment variables

### Technical Details

- Python 3.11+ with Poetry
- Node.js 20+ with npm
- PostgreSQL 14+
- Meilisearch 1.6+
- Nginx for production serving
- Supervisord for process management

---

[0.1.0]: https://github.com/yourusername/folio/releases/tag/v0.1.0

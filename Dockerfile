# Folio - Combined Docker Image
# Multi-stage build: Node for frontend, Python for backend, nginx + supervisord for runtime

# Stage 1: Build frontend
FROM docker.io/library/node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npx vite build

# Stage 2: Install backend dependencies using poetry directly
FROM docker.io/library/python:3.11-slim AS backend-builder
WORKDIR /backend
RUN pip install --no-cache-dir poetry
COPY backend/pyproject.toml backend/poetry.lock ./
# Install deps into a virtual env we can copy
RUN python -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    poetry config virtualenvs.create false && \
    poetry lock --no-interaction && \
    poetry install --no-interaction --no-ansi --no-root --only main && \
    pip install psycopg2-binary

# Stage 3: Runtime
FROM docker.io/library/python:3.11-slim

# Install nginx and supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=backend-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy backend code
WORKDIR /app
COPY backend/ ./

# Copy frontend build
COPY --from=frontend-builder /frontend/dist /var/www/html

# Copy config files
RUN rm -f /etc/nginx/sites-enabled/default
COPY docker/nginx.conf /etc/nginx/conf.d/folio.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/folio.conf
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

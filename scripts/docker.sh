#!/usr/bin/env bash
# Mundaneum Docker Management Script
# Works around Guix docker-compose issues by using docker-cli directly

set -euo pipefail

# Configuration (override with environment variables)
MUNDANEUM_PORT="${MUNDANEUM_PORT:-8080}"
DB_PORT="${DB_PORT:-15432}"
MEILI_PORT="${MEILI_PORT:-17700}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-mundaneum}"
BIB_DIRECTORY="${BIB_DIRECTORY:-}"
DOCS_DIRECTORY="${DOCS_DIRECTORY:-/home/b/documents}"  # Where PDFs are stored
S2_DATA_DIR="${S2_DATA_DIR:-/data/s2}"  # DuckDB S2 corpus
NETWORK_NAME="mundaneum-net"

# Get real Docker CLI (Guix wraps 'docker' as podman)
DOCKER="${DOCKER_CMD:-guix shell docker-cli -- docker}"

show_help() {
    echo "Mundaneum Docker Management"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  build     Build Docker image"
    echo "  start     Start all containers"
    echo "  stop      Stop all containers"
    echo "  status    Show container status"
    echo "  logs      Show mundaneum container logs"
    echo "  shell     Open shell in mundaneum container"
    echo "  clean     Remove all Mundaneum containers and images"
    echo ""
    echo "Environment variables:"
    echo "  MUNDANEUM_PORT         Web UI port (default: 8080)"
    echo "  DB_PORT            PostgreSQL port (default: 15432)"
    echo "  MEILI_PORT         Meilisearch port (default: 17700)"
    echo "  POSTGRES_PASSWORD  Database password (default: mundaneum)"
    echo "  BIB_DIRECTORY      Path to BibTeX files (default: ./data)"
    echo "  DOCKER_CMD         Docker command override (default: guix shell docker-cli -- docker)"
    echo ""
}

build_image() {
    echo "Building mundaneum image..."
    $DOCKER build --network=host -t mundaneum .
    
    echo "Done! Image built:"
    $DOCKER images | grep mundaneum
}

create_network() {
    $DOCKER network inspect $NETWORK_NAME >/dev/null 2>&1 || \
        $DOCKER network create $NETWORK_NAME
}

wait_for_postgres() {
    local max_attempts=30
    local attempt=1
    echo "Waiting for PostgreSQL to be ready..."
    while [ $attempt -le $max_attempts ]; do
        if $DOCKER exec mundaneum-db pg_isready -U mundaneum >/dev/null 2>&1; then
            echo "PostgreSQL is ready."
            return 0
        fi
        echo "  Attempt $attempt/$max_attempts..."
        sleep 1
        attempt=$((attempt + 1))
    done
    echo "ERROR: PostgreSQL failed to start within $max_attempts seconds"
    return 1
}

start_postgres() {
    echo "Starting PostgreSQL..."
    $DOCKER run -d \
        --name mundaneum-db \
        --network $NETWORK_NAME \
        -e POSTGRES_USER=mundaneum \
        -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
        -e POSTGRES_DB=mundaneum \
        -p $DB_PORT:5432 \
        -v mundaneum_postgres:/var/lib/postgresql/data \
        docker.io/library/postgres:16-alpine
    
    wait_for_postgres
}

start_meilisearch() {
    echo "Starting Meilisearch..."
    $DOCKER run -d \
        --name mundaneum-search \
        --network $NETWORK_NAME \
        -e MEILI_ENV=development \
        -e MEILI_NO_ANALYTICS=true \
        -p $MEILI_PORT:7700 \
        -v mundaneum_meili:/meili_data \
        docker.io/getmeili/meilisearch:v1.6
}

start_mundaneum() {
    echo "Starting Mundaneum..."
    
    # Prepare volume mounts
    local mounts=""
    
    # Bibliography mount (optional, for importing)
    if [ -n "$BIB_DIRECTORY" ] && [ -d "$BIB_DIRECTORY" ]; then
        mounts="$mounts -v $BIB_DIRECTORY:/bibliography:ro"
        echo "  Bibliography: $BIB_DIRECTORY → /bibliography"
    fi
    
    # Documents mount (for PDF files - mount at same path so absolute paths work)
    if [ -n "$DOCS_DIRECTORY" ] && [ -d "$DOCS_DIRECTORY" ]; then
        mounts="$mounts -v $DOCS_DIRECTORY:$DOCS_DIRECTORY:ro"
        echo "  Documents: $DOCS_DIRECTORY"
    fi
    
    # S2 corpus mount (DuckDB database)
    if [ -n "$S2_DATA_DIR" ] && [ -d "$S2_DATA_DIR" ]; then
        mounts="$mounts -v $S2_DATA_DIR:/data/s2:ro"
        echo "  S2 Corpus: $S2_DATA_DIR → /data/s2"
    fi
    
    $DOCKER run -d \
        --name mundaneum \
        --network $NETWORK_NAME \
        -p $MUNDANEUM_PORT:8080 \
        -e DB_HOST=mundaneum-db \
        -e DB_PORT=5432 \
        -e DATABASE_URL=postgresql://mundaneum:$POSTGRES_PASSWORD@mundaneum-db:5432/mundaneum \
        -e MEILI_URL=http://mundaneum-search:7700 \
        -e S2_CORPUS_PATH=/data/s2/corpus.duckdb \
        $mounts \
        mundaneum
}

start_all() {
    create_network
    start_postgres
    start_meilisearch
    start_mundaneum
    
    echo ""
    echo "==================================="
    echo "Mundaneum is running!"
    echo "==================================="
    echo "Web UI:      http://localhost:$MUNDANEUM_PORT"
    echo "Database:    localhost:$DB_PORT"
    echo "Meilisearch: http://localhost:$MEILI_PORT"
    echo ""
}

stop_all() {
    echo "Stopping containers..."
    $DOCKER stop mundaneum mundaneum-search mundaneum-db 2>/dev/null || true
    $DOCKER rm mundaneum mundaneum-search mundaneum-db 2>/dev/null || true
    echo "Done."
}

show_status() {
    $DOCKER ps --filter "name=mundaneum" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

show_logs() {
    $DOCKER logs -f --tail 50 mundaneum
}

open_shell() {
    $DOCKER exec -it mundaneum /bin/bash
}

clean_all() {
    echo "Stopping and removing containers..."
    stop_all
    
    echo "Removing images..."
    $DOCKER rmi mundaneum mundaneum-backend mundaneum-frontend 2>/dev/null || true
    
    echo "Removing volumes (data will be lost)..."
    $DOCKER volume rm mundaneum_postgres mundaneum_meili 2>/dev/null || true
    
    echo "Removing network..."
    $DOCKER network rm $NETWORK_NAME 2>/dev/null || true
    
    echo "Clean complete."
}

# Main
case "${1:-help}" in
    build)  build_image ;;
    start)  start_all ;;
    stop)   stop_all ;;
    status) show_status ;;
    logs)   show_logs ;;
    shell)  open_shell ;;
    clean)  clean_all ;;
    *)      show_help ;;
esac

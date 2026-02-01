#!/usr/bin/env bash
# Folio Docker Management Script
# Works around Guix docker-compose issues by using docker-cli directly

set -euo pipefail

# Configuration (override with environment variables)
FOLIO_PORT="${FOLIO_PORT:-8080}"
DB_PORT="${DB_PORT:-15432}"
MEILI_PORT="${MEILI_PORT:-17700}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-folio}"
BIB_DIRECTORY="${BIB_DIRECTORY:-}"
NETWORK_NAME="folio-net"

# Get real Docker CLI (Guix wraps 'docker' as podman)
DOCKER="guix shell docker-cli -- docker"

show_help() {
    echo "Folio Docker Management"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  build     Build Docker image"
    echo "  start     Start all containers"
    echo "  stop      Stop all containers"
    echo "  status    Show container status"
    echo "  logs      Show folio container logs"
    echo "  shell     Open shell in folio container"
    echo "  clean     Remove all Folio containers and images"
    echo ""
    echo "Environment variables:"
    echo "  FOLIO_PORT         Web UI port (default: 8080)"
    echo "  DB_PORT            PostgreSQL port (default: 15432)"
    echo "  MEILI_PORT         Meilisearch port (default: 17700)"
    echo "  POSTGRES_PASSWORD  Database password (default: folio)"
    echo "  BIB_DIRECTORY      Path to BibTeX files (default: ./data)"
    echo ""
}

build_image() {
    echo "Building folio image..."
    $DOCKER build --network=host -t folio .
    
    echo "Done! Image built:"
    $DOCKER images | grep folio
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
        if $DOCKER exec folio-db pg_isready -U folio >/dev/null 2>&1; then
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
        --name folio-db \
        --network $NETWORK_NAME \
        -e POSTGRES_USER=folio \
        -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
        -e POSTGRES_DB=folio \
        -p $DB_PORT:5432 \
        -v folio_postgres:/var/lib/postgresql/data \
        docker.io/library/postgres:16-alpine
    
    wait_for_postgres
}

start_meilisearch() {
    echo "Starting Meilisearch..."
    $DOCKER run -d \
        --name folio-search \
        --network $NETWORK_NAME \
        -e MEILI_ENV=development \
        -e MEILI_NO_ANALYTICS=true \
        -p $MEILI_PORT:7700 \
        -v folio_meili:/meili_data \
        docker.io/getmeili/meilisearch:v1.6
}

start_folio() {
    echo "Starting Folio..."
    
    # Prepare volume mounts
    local mounts=""
    
    # Bibliography mount (optional, for importing)
    if [ -n "$BIB_DIRECTORY" ] && [ -d "$BIB_DIRECTORY" ]; then
        mounts="$mounts -v $BIB_DIRECTORY:/bibliography:ro"
        echo "  Bibliography: $BIB_DIRECTORY → /bibliography"
    fi
    
    $DOCKER run -d \
        --name folio \
        --network host \
        -e DB_HOST=127.0.0.1 \
        -e DB_PORT=$DB_PORT \
        -e DATABASE_URL=postgresql://folio:$POSTGRES_PASSWORD@127.0.0.1:$DB_PORT/folio \
        -e MEILI_URL=http://127.0.0.1:$MEILI_PORT \
        $mounts \
        folio
}

start_all() {
    create_network
    start_postgres
    start_meilisearch
    start_folio
    
    echo ""
    echo "==================================="
    echo "Folio is running!"
    echo "==================================="
    echo "Web UI:      http://localhost:$FOLIO_PORT"
    echo "Database:    localhost:$DB_PORT"
    echo "Meilisearch: http://localhost:$MEILI_PORT"
    echo ""
}

stop_all() {
    echo "Stopping containers..."
    $DOCKER stop folio folio-search folio-db 2>/dev/null || true
    $DOCKER rm folio folio-search folio-db 2>/dev/null || true
    echo "Done."
}

show_status() {
    $DOCKER ps --filter "name=folio" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

show_logs() {
    $DOCKER logs -f --tail 50 folio
}

open_shell() {
    $DOCKER exec -it folio /bin/bash
}

clean_all() {
    echo "Stopping and removing containers..."
    stop_all
    
    echo "Removing images..."
    $DOCKER rmi folio folio-backend folio-frontend 2>/dev/null || true
    
    echo "Removing volumes (data will be lost)..."
    $DOCKER volume rm folio_postgres folio_meili 2>/dev/null || true
    
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

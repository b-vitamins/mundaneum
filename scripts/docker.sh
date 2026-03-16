#!/usr/bin/env bash
# Mundaneum Docker Management Script

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"

# Configuration (override with environment variables)
MUNDANEUM_PORT="${MUNDANEUM_PORT:-8080}"
DB_PORT="${DB_PORT:-15432}"
MEILI_PORT="${MEILI_PORT:-17700}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-mundaneum}"
BIBLIOGRAPHY_REPO_URL="${BIBLIOGRAPHY_REPO_URL:-https://github.com/b-vitamins/bibliography/}"
BIBLIOGRAPHY_REPO_REF="${BIBLIOGRAPHY_REPO_REF:-}"
BIBLIOGRAPHY_HOST_CACHE="${BIBLIOGRAPHY_HOST_CACHE:-$REPO_ROOT/.cache/bibliography}"
BIBLIOGRAPHY_SYNC_TIMEOUT_SECONDS="${BIBLIOGRAPHY_SYNC_TIMEOUT_SECONDS:-300}"
BIBLIOGRAPHY_RUNTIME_SYNC_ENABLED="${BIBLIOGRAPHY_RUNTIME_SYNC_ENABLED:-false}"
NER_DATA_DIR="${NER_DATA_DIR:-/home/b/projects/ner-gold/artifacts/signals-product}"
NER_AUTO_INGEST_ENABLED="${NER_AUTO_INGEST_ENABLED:-true}"
NER_AUTO_INGEST_WAIT_FOR_ENTRIES="${NER_AUTO_INGEST_WAIT_FOR_ENTRIES:-true}"
NER_AUTO_INGEST_WAIT_TIMEOUT_SECONDS="${NER_AUTO_INGEST_WAIT_TIMEOUT_SECONDS:-1800}"
NER_AUTO_INGEST_POLL_INTERVAL_SECONDS="${NER_AUTO_INGEST_POLL_INTERVAL_SECONDS:-5}"
DOCS_DIRECTORY="${DOCS_DIRECTORY:-/home/b/documents}"
S2_DATA_DIR="${S2_DATA_DIR:-/data/s2}"
NETWORK_NAME="mundaneum-net"

IFS=' ' read -r -a DOCKER_CMD_ARR <<< "${DOCKER_CMD:-guix shell docker-cli -- docker}"

run_docker() {
    "${DOCKER_CMD_ARR[@]}" "$@"
}

show_help() {
    echo "Mundaneum Docker Management"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  build              Build Docker image"
    echo "  sync-bibliography  Clone or update the bibliography checkout on the host"
    echo "  start              Start all containers"
    echo "  stop               Stop all containers"
    echo "  status             Show container status"
    echo "  logs               Show mundaneum container logs"
    echo "  shell              Open shell in mundaneum container"
    echo "  clean              Remove all Mundaneum containers and images"
    echo ""
    echo "Environment variables:"
    echo "  MUNDANEUM_PORT                 Web UI port (default: 8080)"
    echo "  DB_PORT                        PostgreSQL port (default: 15432)"
    echo "  MEILI_PORT                     Meilisearch port (default: 17700)"
    echo "  POSTGRES_PASSWORD              Database password (default: mundaneum)"
    echo "  BIBLIOGRAPHY_REPO_URL          Bibliography git remote"
    echo "  BIBLIOGRAPHY_REPO_REF          Optional branch/tag/ref to checkout"
    echo "  BIBLIOGRAPHY_HOST_CACHE        Host checkout path (default: ./.cache/bibliography)"
    echo "  BIBLIOGRAPHY_SYNC_TIMEOUT_SECONDS  In-app git timeout in seconds (default: 300)"
    echo "  BIBLIOGRAPHY_RUNTIME_SYNC_ENABLED  Allow in-container git pull/clone (default: false)"
    echo "  NER_DATA_DIR                   Host signals-product directory to mount (optional)"
    echo "  NER_AUTO_INGEST_ENABLED        Auto-ingest newest NER release at startup (default: true)"
    echo "  NER_AUTO_INGEST_WAIT_FOR_ENTRIES  Wait for bibliography entries before NER ingest (default: true)"
    echo "  NER_AUTO_INGEST_WAIT_TIMEOUT_SECONDS  Max wait for entries (default: 1800)"
    echo "  NER_AUTO_INGEST_POLL_INTERVAL_SECONDS  Entry readiness poll interval (default: 5)"
    echo "  DOCKER_CMD                     Docker command override"
    echo ""
}

build_image() {
    echo "Building mundaneum image..."
    run_docker build --network=host -t mundaneum .

    echo "Done! Image built:"
    run_docker images | grep mundaneum || true
}

require_git() {
    if ! command -v git >/dev/null 2>&1; then
        echo "ERROR: git is required to sync the bibliography checkout"
        exit 1
    fi
}

run_git() {
    GIT_TERMINAL_PROMPT=0 git "$@"
}

normalize_repo_url() {
    printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed 's#/*$##; s#\\.git$##'
}

resolve_checkout_target() {
    local cache_dir="$1"

    if [ -n "$BIBLIOGRAPHY_REPO_REF" ]; then
        printf '%s' "$BIBLIOGRAPHY_REPO_REF"
        return 0
    fi

    run_git -C "$cache_dir" remote set-head origin -a >/dev/null 2>&1 || true
    local remote_head
    remote_head="$(run_git -C "$cache_dir" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)"
    if [ -n "$remote_head" ]; then
        printf '%s' "${remote_head#origin/}"
        return 0
    fi

    local current_branch
    current_branch="$(run_git -C "$cache_dir" branch --show-current 2>/dev/null || true)"
    if [ -n "$current_branch" ]; then
        printf '%s' "$current_branch"
        return 0
    fi

    echo "ERROR: unable to determine bibliography default branch"
    exit 1
}

sync_bibliography_repo() {
    require_git

    local cache_dir
    cache_dir="$(mkdir -p "$(dirname -- "$BIBLIOGRAPHY_HOST_CACHE")" && cd -- "$(dirname -- "$BIBLIOGRAPHY_HOST_CACHE")" && pwd -P)/$(basename -- "$BIBLIOGRAPHY_HOST_CACHE")"

    echo "Checking bibliography remote accessibility..."
    if ! run_git ls-remote --exit-code "$BIBLIOGRAPHY_REPO_URL" HEAD >/dev/null 2>&1; then
        echo "ERROR: unable to reach bibliography remote: $BIBLIOGRAPHY_REPO_URL"
        exit 1
    fi

    if [ -d "$cache_dir/.git" ]; then
        local remote_url
        remote_url="$(run_git -C "$cache_dir" remote get-url origin)"
        if [ "$(normalize_repo_url "$remote_url")" != "$(normalize_repo_url "$BIBLIOGRAPHY_REPO_URL")" ]; then
            echo "ERROR: $cache_dir points at $remote_url, expected $BIBLIOGRAPHY_REPO_URL"
            exit 1
        fi

        echo "Updating bibliography checkout at $cache_dir"
        local target_ref
        target_ref="$(resolve_checkout_target "$cache_dir")"
        run_git -C "$cache_dir" fetch --depth 1 --progress origin "$target_ref"
        if [ -n "$BIBLIOGRAPHY_REPO_REF" ]; then
            run_git -C "$cache_dir" checkout --detach FETCH_HEAD
        else
            run_git -C "$cache_dir" checkout -B "$target_ref" "origin/$target_ref"
        fi
    else
        if [ -d "$cache_dir" ] && [ -n "$(find "$cache_dir" -mindepth 1 -maxdepth 1 2>/dev/null)" ]; then
            echo "ERROR: bibliography cache path exists and is not an empty git repo: $cache_dir"
            exit 1
        fi

        rm -rf "$cache_dir"
        echo "Cloning bibliography repository into $cache_dir"
        local -a clone_args=(clone --depth 1 --progress)
        if [ -n "$BIBLIOGRAPHY_REPO_REF" ]; then
            clone_args+=(--branch "$BIBLIOGRAPHY_REPO_REF")
        fi
        clone_args+=("$BIBLIOGRAPHY_REPO_URL" "$cache_dir")
        run_git "${clone_args[@]}"
    fi

    BIBLIOGRAPHY_HOST_CACHE="$cache_dir"
    local checkout_rev
    checkout_rev="$(run_git -C "$cache_dir" rev-parse --short HEAD)"
    echo "Bibliography checkout ready:"
    echo "  Repo:  $BIBLIOGRAPHY_REPO_URL"
    echo "  Cache: $BIBLIOGRAPHY_HOST_CACHE"
    echo "  Rev:   $checkout_rev"
}

create_network() {
    run_docker network inspect "$NETWORK_NAME" >/dev/null 2>&1 || \
        run_docker network create "$NETWORK_NAME"
}

wait_for_postgres() {
    local max_attempts=30
    local attempt=1
    echo "Waiting for PostgreSQL to be ready..."
    while [ "$attempt" -le "$max_attempts" ]; do
        if run_docker exec mundaneum-db pg_isready -U mundaneum >/dev/null 2>&1; then
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
    run_docker run -d \
        --name mundaneum-db \
        --network "$NETWORK_NAME" \
        -e POSTGRES_USER=mundaneum \
        -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
        -e POSTGRES_DB=mundaneum \
        -p "$DB_PORT:5432" \
        -v mundaneum_postgres:/var/lib/postgresql/data \
        docker.io/library/postgres:16-alpine

    wait_for_postgres
}

start_meilisearch() {
    echo "Starting Meilisearch..."
    run_docker run -d \
        --name mundaneum-search \
        --network "$NETWORK_NAME" \
        -e MEILI_ENV=development \
        -e MEILI_NO_ANALYTICS=true \
        -p "$MEILI_PORT:7700" \
        -v mundaneum_meili:/meili_data \
        docker.io/getmeili/meilisearch:v1.6
}

start_mundaneum() {
    echo "Starting Mundaneum..."
    sync_bibliography_repo

    local -a args=(
        run -d
        --name mundaneum
        --network "$NETWORK_NAME"
        -p "$MUNDANEUM_PORT:8080"
        -e DB_HOST=mundaneum-db
        -e DB_PORT=5432
        -e "DATABASE_URL=postgresql://mundaneum:$POSTGRES_PASSWORD@mundaneum-db:5432/mundaneum"
        -e MEILI_URL=http://mundaneum-search:7700
        -e "BIBLIOGRAPHY_REPO_URL=$BIBLIOGRAPHY_REPO_URL"
        -e BIBLIOGRAPHY_CHECKOUT_PATH=/var/lib/mundaneum/bibliography
        -e "BIBLIOGRAPHY_REPO_REF=$BIBLIOGRAPHY_REPO_REF"
        -e "BIBLIOGRAPHY_SYNC_TIMEOUT_SECONDS=$BIBLIOGRAPHY_SYNC_TIMEOUT_SECONDS"
        -e "BIBLIOGRAPHY_RUNTIME_SYNC_ENABLED=$BIBLIOGRAPHY_RUNTIME_SYNC_ENABLED"
        -e NER_SIGNALS_PATH=/data/ner/signals-product
        -e "NER_AUTO_INGEST_ENABLED=$NER_AUTO_INGEST_ENABLED"
        -e "NER_AUTO_INGEST_WAIT_FOR_ENTRIES=$NER_AUTO_INGEST_WAIT_FOR_ENTRIES"
        -e "NER_AUTO_INGEST_WAIT_TIMEOUT_SECONDS=$NER_AUTO_INGEST_WAIT_TIMEOUT_SECONDS"
        -e "NER_AUTO_INGEST_POLL_INTERVAL_SECONDS=$NER_AUTO_INGEST_POLL_INTERVAL_SECONDS"
        -e S2_CORPUS_PATH=/data/s2/corpus.duckdb
        -v "$BIBLIOGRAPHY_HOST_CACHE:/var/lib/mundaneum/bibliography"
    )

    echo "  Bibliography Cache: $BIBLIOGRAPHY_HOST_CACHE → /var/lib/mundaneum/bibliography"

    if [ -n "$DOCS_DIRECTORY" ] && [ -d "$DOCS_DIRECTORY" ]; then
        args+=(-v "$DOCS_DIRECTORY:$DOCS_DIRECTORY:ro")
        echo "  Documents: $DOCS_DIRECTORY"
    fi

    if [ -n "$S2_DATA_DIR" ] && [ -d "$S2_DATA_DIR" ]; then
        args+=(-v "$S2_DATA_DIR:/data/s2:ro")
        echo "  S2 Corpus: $S2_DATA_DIR → /data/s2"
    fi

    if [ -n "$NER_DATA_DIR" ] && [ -d "$NER_DATA_DIR" ]; then
        args+=(-v "$NER_DATA_DIR:/data/ner/signals-product:ro")
        echo "  NER Signals: $NER_DATA_DIR → /data/ner/signals-product"
    fi

    args+=(mundaneum)
    run_docker "${args[@]}"
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
    run_docker stop mundaneum mundaneum-search mundaneum-db 2>/dev/null || true
    run_docker rm mundaneum mundaneum-search mundaneum-db 2>/dev/null || true
    echo "Done."
}

show_status() {
    run_docker ps --filter "name=mundaneum" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

show_logs() {
    run_docker logs -f --tail 50 mundaneum
}

open_shell() {
    run_docker exec -it mundaneum /bin/bash
}

clean_all() {
    echo "Stopping and removing containers..."
    stop_all

    echo "Removing images..."
    run_docker rmi mundaneum mundaneum-backend mundaneum-frontend 2>/dev/null || true

    echo "Removing volumes (data will be lost)..."
    run_docker volume rm mundaneum_postgres mundaneum_meili 2>/dev/null || true

    echo "Removing network..."
    run_docker network rm "$NETWORK_NAME" 2>/dev/null || true

    echo "Clean complete."
    echo "Bibliography cache retained at: $BIBLIOGRAPHY_HOST_CACHE"
}

case "${1:-help}" in
    build) build_image ;;
    sync-bibliography) sync_bibliography_repo ;;
    start) start_all ;;
    stop) stop_all ;;
    status) show_status ;;
    logs) show_logs ;;
    shell) open_shell ;;
    clean) clean_all ;;
    *) show_help ;;
esac

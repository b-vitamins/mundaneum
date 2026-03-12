# Guix Deployment Guide

This document describes how to deploy Mundaneum as an OCI container on a Guix system.

## Prerequisites

1. **Running services** (via `oci-container-service-type` or native Guix services):

   - PostgreSQL with a `mundaneum` database
   - Meilisearch
   - Qdrant (optional, for embeddings)
   - HuggingFace Text Embeddings Inference (optional, for embeddings)

2. **Credentials file**: Create `/root/mundaneum-db.credentials` with your PostgreSQL password.

## OCI Container Definition

Add to your `oci-containers.scm`:

```scheme
(define mundaneum-db-password
  (read-secret "/root/mundaneum-db.credentials"))

(define oci-mundaneum-service-type
  (oci-container-configuration
    (image "ghcr.io/b-vitamins/mundaneum:latest")
    (network "host")
    (ports '(("8080" . "8080")))
    (volumes (list
               ;; Persistent app state for the bibliography checkout cache
               '("/var/lib/mundaneum" . "/var/lib/mundaneum")))
    (environment
      `(("DATABASE_URL" . ,(string-append
                            "postgresql://mundaneum:"
                            mundaneum-db-password
                            "@localhost:5432/mundaneum"))
        ("MEILI_URL" . "http://localhost:7700")
        ("MEILI_API_KEY" . ,meili-master-key)
        ("QDRANT_URL" . "http://localhost:6333")
        ("EMBEDDINGS_URL" . "http://localhost:8081")
        ("BIBLIOGRAPHY_REPO_URL" . "https://github.com/b-vitamins/bibliography/")
        ("BIBLIOGRAPHY_CHECKOUT_PATH" . "/var/lib/mundaneum/bibliography")
        ("BIBLIOGRAPHY_SYNC_TIMEOUT_SECONDS" . "300")
        ("BIBLIOGRAPHY_RUNTIME_SYNC_ENABLED" . "true")))))
```

## System Configuration

Add to your system services in `mileva.scm` (or similar):

```scheme
(service oci-container-service-type
         (list oci-meilisearch-service-type
               oci-qdrant-service-type
               oci-mundaneum-service-type))  ; Add this line
```

## PostgreSQL Setup

Add a role for Mundaneum:

```scheme
(service postgresql-role-service-type
         (postgresql-role-configuration
           (roles (list (postgresql-role
                          (name "mundaneum")
                          (create-database? #t)
                          (permissions '(createdb login)))))))
```

## Deployment Steps

1. **Build locally** (optional, to test):

   ```bash
   cd /path/to/mundaneum
   docker build -t mundaneum:test .
   ```

2. **Push to GHCR** (handled by CI on git push):

   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. **Reconfigure system**:

   ```bash
   sudo guix system reconfigure /path/to/mileva.scm
   ```

4. **Verify**:
   ```bash
   curl http://localhost:8080/health
   ```

## Data Volumes

| Volume               | Mount Point          | Purpose              |
| -------------------- | -------------------- | -------------------- |
| `/var/lib/mundaneum` | `/var/lib/mundaneum` | App cache (optional) |

Note: PostgreSQL data is managed by the native `postgresql-service-type`, not this container.

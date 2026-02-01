# Guix Deployment Guide

This document describes how to deploy Folio as an OCI container on a Guix system.

## Prerequisites

1. **Running services** (via `oci-container-service-type` or native Guix services):
   - PostgreSQL with a `folio` database
   - Meilisearch
   - Qdrant (optional, for embeddings)
   - HuggingFace Text Embeddings Inference (optional, for embeddings)

2. **Credentials file**: Create `/root/folio-db.credentials` with your PostgreSQL password.

## OCI Container Definition

Add to your `oci-containers.scm`:

```scheme
(define folio-db-password
  (read-secret "/root/folio-db.credentials"))

(define oci-folio-service-type
  (oci-container-configuration
    (image "ghcr.io/YOUR_USERNAME/folio:latest")
    (network "host")
    (ports '(("8080" . "8080")))
    (volumes (list 
               ;; BibTeX files and PDFs (read-only source of truth)
               '("/data/bibliography" . "/data")
               ;; Persistent app state (optional, for caching)
               '("/var/lib/folio" . "/var/lib/folio")))
    (environment 
      `(("DATABASE_URL" . ,(string-append 
                            "postgresql://folio:" 
                            folio-db-password 
                            "@localhost:5432/folio"))
        ("MEILI_URL" . "http://localhost:7700")
        ("MEILI_API_KEY" . ,meili-master-key)
        ("QDRANT_URL" . "http://localhost:6333")
        ("EMBEDDINGS_URL" . "http://localhost:8081")
        ("BIB_DIRECTORY" . "/data")))))
```

## System Configuration

Add to your system services in `mileva.scm` (or similar):

```scheme
(service oci-container-service-type
         (list oci-meilisearch-service-type
               oci-qdrant-service-type
               oci-folio-service-type))  ; Add this line
```

## PostgreSQL Setup

Add a role for Folio:

```scheme
(service postgresql-role-service-type
         (postgresql-role-configuration
           (roles (list (postgresql-role
                          (name "folio")
                          (create-database? #t)
                          (permissions '(createdb login)))))))
```

## Deployment Steps

1. **Build locally** (optional, to test):
   ```bash
   cd /path/to/folio
   docker build -t folio:test .
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

| Volume | Mount Point | Purpose |
|--------|-------------|---------|
| `/data/bibliography` | `/data` | BibTeX files and PDFs (read-only) |
| `/var/lib/folio` | `/var/lib/folio` | App cache (optional) |

Note: PostgreSQL data is managed by the native `postgresql-service-type`, not this container.

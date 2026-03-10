"""
Download helpers for Semantic Scholar dataset shards.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

from app.services.s2_ingest_config import S2_DATASETS_API, URL_REFRESH_INTERVAL

logger = logging.getLogger(__name__)


def _api_get(
    url: str,
    api_key: str | None = None,
    max_retries: int = 5,
) -> httpx.Response:
    """GET with retry and exponential backoff for rate limits."""
    headers = {"x-api-key": api_key} if api_key else {}
    for attempt in range(max_retries):
        resp = httpx.get(url, headers=headers, timeout=30)
        if resp.status_code == 429:
            wait = 2.0 * (2**attempt)
            logger.warning(
                "S2 Datasets API 429, retry in %.1fs (%s)",
                wait,
                url.split("/")[-1],
            )
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp


def get_latest_release(api_key: str | None = None) -> str:
    """Get the latest release date from the S2 Datasets API."""
    resp = _api_get(f"{S2_DATASETS_API}/release/latest", api_key)
    return resp.json()["release_id"]


def get_download_links(
    dataset_name: str,
    release_id: str,
    api_key: str,
) -> list[str]:
    """Get pre-signed S3 download URLs for a dataset's shards."""
    resp = _api_get(
        f"{S2_DATASETS_API}/release/{release_id}/dataset/{dataset_name}",
        api_key,
    )
    return resp.json().get("files", [])


def download_shard(url: str, dest: Path, max_retries: int = 3) -> bool | str:
    """Download one shard, returning success, skip, or URL-expired status."""
    if dest.exists() and dest.stat().st_size > 0:
        logger.info("  ✓ Already exists: %s", dest.name)
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")

    for attempt in range(max_retries):
        if tmp.exists():
            tmp.unlink()

        if attempt > 0:
            wait = 5.0 * (2 ** (attempt - 1))
            logger.warning(
                "  ↻ Retry %d/%d for %s in %.0fs",
                attempt + 1,
                max_retries,
                dest.name,
                wait,
            )
            time.sleep(wait)

        logger.info("  ↓ Downloading: %s", dest.name)
        t0 = time.monotonic()

        try:
            with httpx.stream(
                "GET",
                url,
                timeout=httpx.Timeout(connect=30, read=600, write=30, pool=30),
                follow_redirects=True,
            ) as resp:
                if resp.status_code == 400:
                    logger.warning("  ⚠ URL expired (400) for %s", dest.name)
                    return "expired"
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0

                with open(tmp, "wb") as handle:
                    for chunk in resp.iter_bytes(chunk_size=8 * 1024 * 1024):
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = downloaded / total * 100
                            elapsed = time.monotonic() - t0
                            rate = downloaded / elapsed / 1024 / 1024 if elapsed > 0 else 0
                            print(
                                f"\r    {pct:.1f}% ({rate:.1f} MB/s)",
                                end="",
                                flush=True,
                            )

            print()

            if total > 0 and downloaded < total:
                logger.warning(
                    "  ⚠ Incomplete: got %d/%d bytes for %s",
                    downloaded,
                    total,
                    dest.name,
                )
                continue

            tmp.rename(dest)
            elapsed = time.monotonic() - t0
            size_mb = dest.stat().st_size / 1024 / 1024
            logger.info(
                "  ✓ %s: %.1f MB in %.1fs (%.1f MB/s)",
                dest.name,
                size_mb,
                elapsed,
                size_mb / elapsed if elapsed > 0 else 0,
            )
            return True
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.HTTPStatusError,
            OSError,
        ) as exc:
            print()
            logger.warning(
                "  ✗ Failed %s (attempt %d/%d): %s",
                dest.name,
                attempt + 1,
                max_retries,
                exc,
            )
            continue

    logger.error("  ✗ Gave up on %s after %d attempts", dest.name, max_retries)
    if tmp.exists():
        tmp.unlink()
    return False


def download_dataset(
    dataset_name: str,
    shards_dir: Path,
    api_key: str,
    release_id: str | None = None,
) -> Path:
    """Download all shards for a dataset and write metadata."""
    if not release_id:
        release_id = get_latest_release(api_key)

    logger.info("Downloading '%s' from release %s", dataset_name, release_id)

    urls = get_download_links(dataset_name, release_id, api_key)
    urls_fetched_at = time.monotonic()
    if not urls:
        logger.error("No download links for dataset '%s'", dataset_name)
        raise RuntimeError(f"No download links for {dataset_name}")

    dataset_dir = shards_dir / release_id / dataset_name
    dataset_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    failed = 0

    for index in range(len(urls)):
        shard_name = f"{index:03d}.jsonl.gz"
        dest = dataset_dir / shard_name

        if time.monotonic() - urls_fetched_at > URL_REFRESH_INTERVAL:
            logger.info("  🔄 Refreshing download URLs (older than 30m)...")
            urls = get_download_links(dataset_name, release_id, api_key)
            urls_fetched_at = time.monotonic()

        result = download_shard(urls[index], dest)
        if result == "expired":
            logger.info("  🔄 Refreshing download URLs (expired)...")
            urls = get_download_links(dataset_name, release_id, api_key)
            urls_fetched_at = time.monotonic()
            result = download_shard(urls[index], dest)

        if result is True:
            downloaded += 1
        elif result is False:
            pass
        else:
            failed += 1

    logger.info(
        "Dataset '%s': %d downloaded, %d failed, %d total shards",
        dataset_name,
        downloaded,
        failed,
        len(urls),
    )

    meta_path = dataset_dir / "_meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "dataset": dataset_name,
                "release_id": release_id,
                "shard_count": len(urls),
                "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            indent=2,
        )
    )
    return dataset_dir

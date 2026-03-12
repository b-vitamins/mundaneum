"""
Managed checkout for the canonical bibliography repository.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.logging import get_logger
from app.services.bibliography_contract import iter_bib_files

logger = get_logger(__name__)


class BibliographyRepositoryError(RuntimeError):
    """Raised when the bibliography checkout cannot be prepared."""


@dataclass(frozen=True, slots=True)
class BibliographyCheckoutState:
    repo_url: str
    checkout_path: Path
    exists: bool
    files_count: int


class BibliographyRepositoryService:
    """Clone and update the bibliography checkout used for ingestion."""

    def __init__(
        self,
        *,
        repo_url: str,
        checkout_path: Path,
        ref: str | None = None,
        timeout_seconds: int = 30,
    ):
        self.repo_url = repo_url
        self.checkout_path = checkout_path
        self.ref = ref
        self.timeout_seconds = timeout_seconds
        self._lock = asyncio.Lock()

    async def ensure_checkout(self, *, refresh: bool = True) -> Path:
        """Ensure the configured repository exists locally and is current."""
        async with self._lock:
            return await asyncio.to_thread(self._ensure_checkout_sync, refresh)

    async def describe_checkout(self) -> BibliographyCheckoutState:
        """Report local checkout status without mutating it."""
        return await asyncio.to_thread(self.describe_checkout_sync)

    def describe_checkout_sync(self) -> BibliographyCheckoutState:
        checkout_path = self.checkout_path.resolve()
        exists = checkout_path.is_dir() and (checkout_path / ".git").exists()
        files_count = len(iter_bib_files(checkout_path)) if exists else 0
        return BibliographyCheckoutState(
            repo_url=self.repo_url,
            checkout_path=checkout_path,
            exists=exists,
            files_count=files_count,
        )

    def _ensure_checkout_sync(self, refresh: bool) -> Path:
        git_binary = shutil.which("git")
        if git_binary is None:
            raise BibliographyRepositoryError(
                "git is required to fetch the bibliography repository"
            )

        checkout_path = self.checkout_path.resolve()
        checkout_path.parent.mkdir(parents=True, exist_ok=True)

        if not checkout_path.exists():
            logger.info("Cloning bibliography repository from %s", self.repo_url)
            self._clone_checkout(git_binary, checkout_path)
            return checkout_path

        if not checkout_path.is_dir():
            raise BibliographyRepositoryError(
                f"Bibliography checkout path is not a directory: {checkout_path}"
            )

        if not (checkout_path / ".git").exists():
            if any(checkout_path.iterdir()):
                raise BibliographyRepositoryError(
                    f"Bibliography checkout path is not a git repository: {checkout_path}"
                )
            logger.info(
                "Cloning bibliography repository into empty directory %s", checkout_path
            )
            self._clone_checkout(git_binary, checkout_path)
            return checkout_path

        remote_url = self._run_git_output(
            self._checkout_git_args(git_binary, checkout_path)
            + ["remote", "get-url", "origin"]
        )
        if _normalize_repo_url(remote_url) != _normalize_repo_url(self.repo_url):
            raise BibliographyRepositoryError(
                f"Bibliography checkout at {checkout_path} points at {remote_url}, expected {self.repo_url}"
            )

        if refresh:
            logger.info("Updating bibliography checkout at %s", checkout_path)
            self._refresh_checkout(git_binary, checkout_path)

        return checkout_path

    def _clone_checkout(self, git_binary: str, checkout_path: Path) -> None:
        args = [git_binary, "clone", "--depth", "1"]
        if self.ref:
            args.extend(["--branch", self.ref])
        args.extend([self.repo_url, str(checkout_path)])
        self._run_git(args, cwd=checkout_path.parent)

    def _refresh_checkout(self, git_binary: str, checkout_path: Path) -> None:
        target_ref = self.ref or self._resolve_default_branch(git_binary, checkout_path)
        self._run_git(
            self._checkout_git_args(git_binary, checkout_path)
            + ["fetch", "--depth", "1", "origin", target_ref],
            cwd=checkout_path,
        )
        checkout_args = self._checkout_git_args(git_binary, checkout_path) + [
            "checkout"
        ]
        if self.ref:
            checkout_args.extend(["--detach", "FETCH_HEAD"])
        else:
            checkout_args.extend(["-B", target_ref, f"origin/{target_ref}"])
        self._run_git(checkout_args, cwd=checkout_path)

    def _resolve_default_branch(self, git_binary: str, checkout_path: Path) -> str:
        self._run_git(
            self._checkout_git_args(git_binary, checkout_path)
            + ["remote", "set-head", "origin", "-a"],
            cwd=checkout_path,
        )
        remote_head = self._run_git_output(
            self._checkout_git_args(git_binary, checkout_path)
            + ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"]
        )
        if remote_head.startswith("origin/"):
            return remote_head.removeprefix("origin/")
        raise BibliographyRepositoryError(
            f"Unable to determine default branch for {self.repo_url}"
        )

    def _checkout_git_args(self, git_binary: str, checkout_path: Path) -> list[str]:
        return [
            git_binary,
            "-c",
            f"safe.directory={checkout_path}",
            "-C",
            str(checkout_path),
        ]

    def _run_git(self, args: list[str], *, cwd: Path) -> None:
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        try:
            result = subprocess.run(
                args,
                cwd=cwd,
                capture_output=True,
                text=True,
                env=env,
                check=False,
                timeout=self.timeout_seconds,
            )
            result.check_returncode()
        except subprocess.CalledProcessError:
            message = (
                result.stderr.strip() or result.stdout.strip() or "unknown git error"
            )
            raise BibliographyRepositoryError(message) from None
        except subprocess.TimeoutExpired:
            raise BibliographyRepositoryError(
                f"git command timed out after {self.timeout_seconds} seconds"
            ) from None
        return

    def _run_git_output(self, args: list[str]) -> str:
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                env=env,
                check=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or "unknown git error"
            raise BibliographyRepositoryError(message) from None
        except subprocess.TimeoutExpired:
            raise BibliographyRepositoryError(
                f"git command timed out after {self.timeout_seconds} seconds"
            ) from None
        return result.stdout.strip()


def _normalize_repo_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized.lower()

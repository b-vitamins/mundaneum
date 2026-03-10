"""
DuckDB-backed query execution helpers for the local S2 corpus.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from app.services.s2_corpus_queries import BoundDuckDBQuery

logger = logging.getLogger(__name__)


class DuckDBCorpusStore:
    """Own the thread-local DuckDB connection and execute prepared queries."""

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._local = threading.local()

    def get_connection(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            return conn
        if not self._db_path.exists():
            logger.info("LocalCorpus: DuckDB not found at %s", self._db_path)
            return None

        import duckdb

        conn = duckdb.connect(str(self._db_path), read_only=True)
        self._local.conn = conn
        logger.info(
            "LocalCorpus: connected to %s (thread %s)",
            self._db_path,
            threading.current_thread().name,
        )
        return conn

    def fetchone(self, query: BoundDuckDBQuery) -> Any:
        conn = self.get_connection()
        if conn is None:
            return None
        return query.fetchone(conn)

    def fetchall(self, query: BoundDuckDBQuery) -> list[Any]:
        conn = self.get_connection()
        if conn is None:
            return []
        return query.fetchall(conn)

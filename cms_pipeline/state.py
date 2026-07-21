from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import Distribution


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StateStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    discovered_count INTEGER NOT NULL DEFAULT 0,
                    selected_count INTEGER NOT NULL DEFAULT 0,
                    succeeded_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    message TEXT
                );

                CREATE TABLE IF NOT EXISTS dataset_state (
                    distribution_key TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    dataset_title TEXT NOT NULL,
                    distribution_index INTEGER NOT NULL,
                    source_url TEXT NOT NULL,
                    source_modified TEXT NOT NULL,
                    output_path TEXT,
                    row_count INTEGER,
                    file_size_bytes INTEGER,
                    sha256 TEXT,
                    last_success_at TEXT,
                    last_status TEXT NOT NULL,
                    error_message TEXT
                );
                """
            )

    def start_run(self) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO pipeline_runs(started_at, status)
                VALUES (?, 'RUNNING')
                """,
                (utc_now(),),
            )
            return int(cursor.lastrowid)

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        discovered_count: int,
        selected_count: int,
        succeeded_count: int,
        skipped_count: int,
        failed_count: int,
        message: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE pipeline_runs
                SET completed_at = ?, status = ?, discovered_count = ?,
                    selected_count = ?, succeeded_count = ?, skipped_count = ?,
                    failed_count = ?, message = ?
                WHERE run_id = ?
                """,
                (
                    utc_now(),
                    status,
                    discovered_count,
                    selected_count,
                    succeeded_count,
                    skipped_count,
                    failed_count,
                    message,
                    run_id,
                ),
            )

    def needs_download(self, distribution: Distribution, force: bool = False) -> bool:
        if force:
            return True

        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT source_modified, source_url, last_status, output_path
                FROM dataset_state
                WHERE distribution_key = ?
                """,
                (distribution.key,),
            ).fetchone()

        if row is None:
            return True

        output_exists = bool(row["output_path"]) and Path(row["output_path"]).exists()
        return not (
            row["last_status"] == "SUCCESS"
            and row["source_modified"] == distribution.dataset_modified
            and row["source_url"] == distribution.download_url
            and output_exists
        )

    def record_success(
        self,
        distribution: Distribution,
        *,
        output_path: Path,
        row_count: int,
        file_size_bytes: int,
        sha256: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO dataset_state(
                    distribution_key, dataset_id, dataset_title,
                    distribution_index, source_url, source_modified,
                    output_path, row_count, file_size_bytes, sha256,
                    last_success_at, last_status, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUCCESS', NULL)
                ON CONFLICT(distribution_key) DO UPDATE SET
                    dataset_id = excluded.dataset_id,
                    dataset_title = excluded.dataset_title,
                    distribution_index = excluded.distribution_index,
                    source_url = excluded.source_url,
                    source_modified = excluded.source_modified,
                    output_path = excluded.output_path,
                    row_count = excluded.row_count,
                    file_size_bytes = excluded.file_size_bytes,
                    sha256 = excluded.sha256,
                    last_success_at = excluded.last_success_at,
                    last_status = 'SUCCESS',
                    error_message = NULL
                """,
                (
                    distribution.key,
                    distribution.dataset_id,
                    distribution.dataset_title,
                    distribution.distribution_index,
                    distribution.download_url,
                    distribution.dataset_modified,
                    str(output_path.resolve()),
                    row_count,
                    file_size_bytes,
                    sha256,
                    utc_now(),
                ),
            )

    def record_failure(self, distribution: Distribution, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO dataset_state(
                    distribution_key, dataset_id, dataset_title,
                    distribution_index, source_url, source_modified,
                    last_status, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, 'FAILED', ?)
                ON CONFLICT(distribution_key) DO UPDATE SET
                    dataset_id = excluded.dataset_id,
                    dataset_title = excluded.dataset_title,
                    distribution_index = excluded.distribution_index,
                    source_url = excluded.source_url,
                    source_modified = excluded.source_modified,
                    last_status = 'FAILED',
                    error_message = excluded.error_message
                """,
                (
                    distribution.key,
                    distribution.dataset_id,
                    distribution.dataset_title,
                    distribution.distribution_index,
                    distribution.download_url,
                    distribution.dataset_modified,
                    error[:4000],
                ),
            )

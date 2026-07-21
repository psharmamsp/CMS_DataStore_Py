from __future__ import annotations

import csv
import hashlib
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from .config import Settings
from .models import Distribution
from .naming import unique_snake_case_headers

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessResult:
    distribution: Distribution
    output_path: Path
    row_count: int
    file_size_bytes: int
    sha256: str


def safe_filename(distribution: Distribution) -> str:
    source_name = Path(unquote(urlparse(distribution.download_url).path)).name
    stem = Path(source_name).stem or distribution.dataset_id
    suffix = Path(source_name).suffix.lower() or ".csv"

    cleaned = "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in stem
    ).strip("._")
    cleaned = cleaned or distribution.dataset_id

    return (
        f"{distribution.dataset_id}"
        f"__{distribution.distribution_index}"
        f"__{cleaned}{suffix}"
    )


def request_with_retry(url: str, settings: Settings) -> requests.Response:
    last_error: Exception | None = None

    for attempt in range(1, settings.max_retries + 1):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": settings.user_agent},
                stream=True,
                timeout=(
                    settings.connect_timeout_seconds,
                    settings.read_timeout_seconds,
                ),
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt == settings.max_retries:
                break

            delay = settings.retry_backoff_seconds * (2 ** (attempt - 1))
            LOGGER.warning(
                "Download attempt %s/%s failed for %s; retrying in %.1fs: %s",
                attempt,
                settings.max_retries,
                url,
                delay,
                exc,
            )
            time.sleep(delay)

    raise RuntimeError(f"Download failed after retries: {last_error}")


def download_and_transform(
    distribution: Distribution,
    settings: Settings,
) -> ProcessResult:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    final_path = settings.output_dir / safe_filename(distribution)
    raw_temp_path = final_path.with_suffix(final_path.suffix + ".download")
    processed_temp_path = final_path.with_suffix(final_path.suffix + ".processing")

    for temp_path in (raw_temp_path, processed_temp_path):
        temp_path.unlink(missing_ok=True)

    try:
        with request_with_retry(distribution.download_url, settings) as response:
            with raw_temp_path.open("wb") as raw_file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        raw_file.write(chunk)

        row_count = rewrite_csv_headers(raw_temp_path, processed_temp_path)
        os.replace(processed_temp_path, final_path)
        raw_temp_path.unlink(missing_ok=True)

        digest = sha256_file(final_path)
        return ProcessResult(
            distribution=distribution,
            output_path=final_path,
            row_count=row_count,
            file_size_bytes=final_path.stat().st_size,
            sha256=digest,
        )
    except Exception:
        raw_temp_path.unlink(missing_ok=True)
        processed_temp_path.unlink(missing_ok=True)
        raise


def rewrite_csv_headers(source_path: Path, target_path: Path) -> int:
    """Stream a CSV while replacing only its header row."""
    with source_path.open("r", encoding="utf-8-sig", newline="") as source:
        sample = source.read(65536)
        source.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
        except csv.Error:
            dialect = csv.excel

        reader = csv.reader(source, dialect)
        try:
            original_headers = next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV file is empty: {source_path}") from exc

        normalized_headers = unique_snake_case_headers(original_headers)

        with target_path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.writer(target, dialect)
            writer.writerow(normalized_headers)

            row_count = 0
            for row in reader:
                writer.writerow(row)
                row_count += 1

    return row_count


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for block in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

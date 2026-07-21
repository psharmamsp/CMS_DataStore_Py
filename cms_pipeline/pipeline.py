from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .catalog import fetch_catalog, hospital_csv_distributions
from .config import Settings
from .models import Distribution
from .processor import ProcessResult, download_and_transform
from .state import StateStore

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunSummary:
    run_id: int
    discovered: int
    selected: int
    succeeded: int
    skipped: int
    failed: int


def run_pipeline(
    settings: Settings,
    *,
    force: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
) -> RunSummary:
    store = StateStore(settings.database_path)
    run_id = store.start_run()

    discovered = selected_count = succeeded = skipped = failed = 0

    try:
        catalog = fetch_catalog(settings)
        distributions = hospital_csv_distributions(catalog, settings.theme)
        discovered = len(distributions)

        candidates: list[Distribution] = []
        for distribution in distributions:
            if store.needs_download(distribution, force=force):
                candidates.append(distribution)
            else:
                skipped += 1

        if limit is not None:
            candidates = candidates[:limit]

        selected_count = len(candidates)

        LOGGER.info(
            "Run %s: discovered=%s selected=%s skipped=%s dry_run=%s",
            run_id,
            discovered,
            selected_count,
            skipped,
            dry_run,
        )

        if dry_run:
            for item in candidates:
                LOGGER.info(
                    "WOULD PROCESS | %s | %s | modified=%s | %s",
                    item.dataset_id,
                    item.dataset_title,
                    item.dataset_modified,
                    item.download_url,
                )
        elif candidates:
            with ThreadPoolExecutor(
                max_workers=settings.max_workers,
                thread_name_prefix="cms-download",
            ) as executor:
                future_map = {
                    executor.submit(download_and_transform, item, settings): item
                    for item in candidates
                }

                for future in as_completed(future_map):
                    item = future_map[future]
                    try:
                        result: ProcessResult = future.result()
                        store.record_success(
                            item,
                            output_path=result.output_path,
                            row_count=result.row_count,
                            file_size_bytes=result.file_size_bytes,
                            sha256=result.sha256,
                        )
                        succeeded += 1
                        LOGGER.info(
                            "SUCCESS | %s | rows=%s | bytes=%s | %s",
                            item.dataset_id,
                            result.row_count,
                            result.file_size_bytes,
                            result.output_path,
                        )
                    except Exception as exc:
                        failed += 1
                        store.record_failure(item, str(exc))
                        LOGGER.exception(
                            "FAILED | %s | %s", item.dataset_id, item.dataset_title
                        )

        final_status = "SUCCESS" if failed == 0 else "PARTIAL_FAILURE"
        store.finish_run(
            run_id,
            status=final_status,
            discovered_count=discovered,
            selected_count=selected_count,
            succeeded_count=succeeded,
            skipped_count=skipped,
            failed_count=failed,
        )

        return RunSummary(
            run_id=run_id,
            discovered=discovered,
            selected=selected_count,
            succeeded=succeeded,
            skipped=skipped,
            failed=failed,
        )
    except Exception as exc:
        store.finish_run(
            run_id,
            status="FAILED",
            discovered_count=discovered,
            selected_count=selected_count,
            succeeded_count=succeeded,
            skipped_count=skipped,
            failed_count=failed,
            message=str(exc),
        )
        raise

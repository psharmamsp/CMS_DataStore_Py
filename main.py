from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from cms_pipeline.config import Settings
from cms_pipeline.logging_setup import configure_logging
from cms_pipeline.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download modified CMS Provider Data datasets with theme "
            "'Hospitals', normalize CSV headers, and track state in SQLite."
        )
    )
    parser.add_argument("--force", action="store_true", help="Reprocess all datasets.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List datasets that would be processed without downloading them.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N changed distributions (useful for testing).",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/state/cms_pipeline.db"),
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be at least 1")

    settings = replace(
        Settings(),
        max_workers=args.workers,
        output_dir=args.output_dir,
        database_path=args.database,
    )
    log_path = configure_logging(settings.log_dir, verbose=args.verbose)

    summary = run_pipeline(
        settings,
        force=args.force,
        dry_run=args.dry_run,
        limit=args.limit,
    )

    print(
        f"Run {summary.run_id} completed: "
        f"discovered={summary.discovered}, selected={summary.selected}, "
        f"succeeded={summary.succeeded}, skipped={summary.skipped}, "
        f"failed={summary.failed}. Log: {log_path}"
    )
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

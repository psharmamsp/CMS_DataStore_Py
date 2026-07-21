from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    metastore_url: str = (
        "https://data.cms.gov/provider-data/api/1/"
        "metastore/schemas/dataset/items"
    )
    theme: str = "Hospitals"
    output_dir: Path = Path("data/processed")
    database_path: Path = Path("data/state/cms_pipeline.db")
    log_dir: Path = Path("logs")
    max_workers: int = 8
    connect_timeout_seconds: int = 15
    read_timeout_seconds: int = 300
    max_retries: int = 4
    retry_backoff_seconds: float = 1.0
    user_agent: str = "cms-hospital-pipeline/1.0"

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Distribution:
    dataset_id: str
    dataset_title: str
    dataset_modified: str
    distribution_index: int
    download_url: str
    media_type: str

    @property
    def key(self) -> str:
        return f"{self.dataset_id}:{self.distribution_index}"

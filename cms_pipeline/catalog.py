from __future__ import annotations

from typing import Any

import requests

from .config import Settings
from .models import Distribution


class CatalogError(RuntimeError):
    pass


def fetch_catalog(settings: Settings) -> list[dict[str, Any]]:
    try:
        response = requests.get(
            settings.metastore_url,
            headers={"User-Agent": settings.user_agent},
            timeout=(
                settings.connect_timeout_seconds,
                settings.read_timeout_seconds,
            ),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise CatalogError(f"Unable to read CMS metastore: {exc}") from exc

    if not isinstance(payload, list):
        raise CatalogError("CMS metastore response was not a JSON array.")
    return payload


def hospital_csv_distributions(
    datasets: list[dict[str, Any]],
    theme: str,
) -> list[Distribution]:
    selected: list[Distribution] = []

    for dataset in datasets:
        themes = dataset.get("theme") or []
        if not isinstance(themes, list):
            themes = [themes]

        if not any(str(item).casefold() == theme.casefold() for item in themes):
            continue

        dataset_id = str(dataset.get("identifier", "")).strip()
        title = str(dataset.get("title", dataset_id)).strip()
        modified = str(dataset.get("modified", "")).strip()

        if not dataset_id or not modified:
            continue

        distributions = dataset.get("distribution") or []
        for index, dist in enumerate(distributions):
            if not isinstance(dist, dict):
                continue

            url = str(dist.get("downloadURL", "")).strip()
            media_type = str(dist.get("mediaType", "")).strip().lower()
            is_csv = (
                media_type in {"text/csv", "application/csv"}
                or url.lower().split("?", 1)[0].endswith(".csv")
            )
            if url and is_csv:
                selected.append(
                    Distribution(
                        dataset_id=dataset_id,
                        dataset_title=title,
                        dataset_modified=modified,
                        distribution_index=index,
                        download_url=url,
                        media_type=media_type or "text/csv",
                    )
                )

    return selected

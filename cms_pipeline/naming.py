from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


def to_snake_case(value: str) -> str:
    """Convert an arbitrary CSV header into normalized snake_case."""
    text = unicodedata.normalize("NFKD", str(value))
    text = text.replace("’", "").replace("'", "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_").lower()
    return text or "unnamed_column"


def unique_snake_case_headers(headers: Iterable[str]) -> list[str]:
    """Normalize headers and suffix duplicates deterministically."""
    counts: dict[str, int] = {}
    output: list[str] = []

    for header in headers:
        base = to_snake_case(header)
        count = counts.get(base, 0) + 1
        counts[base] = count
        output.append(base if count == 1 else f"{base}_{count}")

    return output

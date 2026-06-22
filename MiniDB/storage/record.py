from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Record:
    values: dict[str, object]
    row_id: int | None = None


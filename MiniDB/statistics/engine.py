from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
from typing import Any


@dataclass
class TableStatistics:
    row_count: int
    distinct_count: dict[str, int]
    null_count: dict[str, int]
    histogram: dict[str, dict[Any, int]] = field(default_factory=dict)


class StatisticsEngine:
    def table_statistics(self, rows: list[dict[str, object]]) -> TableStatistics:
        if not rows:
            return TableStatistics(0, {}, {})
        columns = rows[0].keys()
        distinct_count = {column: len({row.get(column) for row in rows}) for column in columns}
        null_count = {column: sum(1 for row in rows if row.get(column) is None) for column in columns}
        histogram = {column: dict(Counter(row.get(column) for row in rows)) for column in columns}
        return TableStatistics(len(rows), distinct_count, null_count, histogram)


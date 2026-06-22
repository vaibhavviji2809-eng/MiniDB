from __future__ import annotations

from dataclasses import dataclass, field

from ..errors import StorageError
from ..statistics import StatisticsEngine
from ..types import Column
from .pager import Pager


@dataclass
class ColumnTable:
    name: str
    columns: list[Column]
    pager: Pager
    storage_format: str = "column"
    columns_data: dict[str, list[object]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.columns_data:
            table_data = self.pager.load_table_data(self.name) or {}
            self.columns_data = table_data.get("columns_data", {column.name: [] for column in self.columns})
        for column in self.columns:
            self.columns_data.setdefault(column.name, [])

    def insert(self, values: dict[str, object], tx_id: int | None = None) -> None:
        self._validate(values)
        for column in self.columns:
            self.columns_data[column.name].append(values[column.name])
        self._persist()

    def select_all(self, snapshot_ts: int | None = None, tx_id: int | None = None) -> list[dict[str, object]]:
        row_count = len(next(iter(self.columns_data.values()), []))
        rows = []
        for i in range(row_count):
            row = {column.name: self.columns_data[column.name][i] for column in self.columns}
            rows.append(row)
        return rows

    def statistics(self) -> dict[str, object]:
        rows = self.select_all()
        stats = StatisticsEngine().table_statistics(rows)
        return {
            "row_count": stats.row_count,
            "page_count": 1 if rows else 0,
            "distinct_values": stats.distinct_count,
            "null_count": stats.null_count,
            "histogram": stats.histogram,
        }

    def update(self, predicate, assignments: dict[str, object], tx_id: int | None = None) -> int:
        rows = self.select_all()
        count = 0
        for i, row in enumerate(rows):
            if predicate(row):
                for key, value in assignments.items():
                    self.columns_data[key][i] = value
                count += 1
        if count:
            self._persist()
        return count

    def delete(self, predicate, tx_id: int | None = None) -> int:
        rows = self.select_all()
        keep_indices = [i for i, row in enumerate(rows) if not predicate(row)]
        if len(keep_indices) == len(rows):
            return 0
        for column in self.columns:
            self.columns_data[column.name] = [self.columns_data[column.name][i] for i in keep_indices]
        self._persist()
        return len(rows) - len(keep_indices)

    def find_by_index(self, column: str, operator: str, value: object, snapshot_ts: int | None = None, tx_id: int | None = None) -> list[dict[str, object]]:
        rows = self.select_all()
        results = []
        for row in rows:
            candidate = row.get(column)
            if operator == "=" and candidate == value:
                results.append(row)
            elif operator == ">" and candidate > value:
                results.append(row)
            elif operator == ">=" and candidate >= value:
                results.append(row)
            elif operator == "<" and candidate < value:
                results.append(row)
            elif operator == "<=" and candidate <= value:
                results.append(row)
        return results

    def _validate(self, values: dict[str, object]) -> None:
        expected = {column.name for column in self.columns}
        provided = set(values)
        if expected != provided:
            raise StorageError(f"Expected columns {sorted(expected)}, got {sorted(provided)}")

    def _persist(self) -> None:
        schema = [{"name": column.name, "type": column.type} for column in self.columns]
        self.pager.write_table_data(self.name, {"schema": schema, "storage_format": self.storage_format, "columns_data": self.columns_data})

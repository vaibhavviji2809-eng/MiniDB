from __future__ import annotations

from dataclasses import dataclass, field

from ..errors import StorageError
from ..index import BTreeIndex, HashIndex
from ..statistics import StatisticsEngine
from ..types import Column
from .page import Page
from .pager import Pager
from .record import Record


@dataclass
class Table:
    name: str
    columns: list[Column]
    pager: Pager
    storage_format: str = "row"
    pages: list[Page] = field(default_factory=list)
    indexes: dict[str, object] = field(default_factory=dict)
    next_row_id: int = 1

    def __post_init__(self) -> None:
        if not self.pages:
            self.pages = self.pager.load_table_pages(self.name)
        self._ensure_indexes()
        self._rebuild_row_counter()

    def _ensure_indexes(self) -> None:
        for column in self.columns:
            if column.type == "INT":
                self.indexes.setdefault(column.name, BTreeIndex())
            else:
                self.indexes.setdefault(column.name, HashIndex())
        self._rebuild_indexes()

    def _rebuild_row_counter(self) -> None:
        row_ids = [record.row_id for record in self.iter_records() if record.row_id is not None]
        self.next_row_id = max(row_ids, default=0) + 1

    def _rebuild_indexes(self) -> None:
        for index in self.indexes.values():
            if hasattr(index, "keys"):
                index.keys = []
                index.values = []
            elif hasattr(index, "bitmaps"):
                index.bitmaps = {}
            elif hasattr(index, "_index"):
                index._index = {}
        for record in self.iter_records():
            values = record.visible_version(self.pager.current_clock())
            if values is not None:
                self._index_record(record, values)

    def _index_record(self, record: Record, values: dict[str, object] | None = None) -> None:
        values = values or record.values or {}
        for column_name, index in self.indexes.items():
            index.insert(values.get(column_name), record.row_id)

    def _deindex_record(self, record: Record, values: dict[str, object] | None = None) -> None:
        values = values or record.values or {}
        for column_name, index in self.indexes.items():
            index.delete(values.get(column_name), record.row_id)

    def iter_records(self):
        for page in self.pages:
            for record in page.records:
                yield record

    def insert(self, values: dict[str, object], tx_id: int | None = None) -> Record:
        self._validate(values)
        ts = self.pager.next_timestamp()
        record = Record(values=values, row_id=self.next_row_id)
        record.add_version(values, tx_id=tx_id, commit_ts=ts, committed=True)
        self.next_row_id += 1
        if not self.pages or self.pages[-1].is_full():
            self.pages.append(Page(len(self.pages)))
        self.pages[-1].records.append(record)
        self._rebuild_indexes()
        self._persist()
        return record

    def select_all(self, snapshot_ts: int | None = None, tx_id: int | None = None) -> list[dict[str, object]]:
        snapshot_ts = snapshot_ts if snapshot_ts is not None else self.pager.current_clock()
        rows = []
        for record in self.iter_records():
            values = record.visible_version(snapshot_ts, tx_id=tx_id)
            if values is not None:
                rows.append(values)
        return rows

    def statistics(self) -> dict[str, object]:
        rows = self.select_all()
        stats = StatisticsEngine().table_statistics(rows)
        return {
            "row_count": stats.row_count,
            "page_count": len(self.pages),
            "distinct_values": stats.distinct_count,
            "null_count": stats.null_count,
            "histogram": stats.histogram,
        }

    def update(self, predicate, assignments: dict[str, object], tx_id: int | None = None) -> int:
        count = 0
        for page in self.pages:
            for record in page.records:
                current = record.visible_version(self.pager.current_clock(), tx_id=tx_id)
                if current is not None and predicate(current):
                    new_values = dict(current)
                    new_values.update(assignments)
                    ts = self.pager.next_timestamp()
                    record.add_version(new_values, tx_id=tx_id, commit_ts=ts, committed=True)
                    count += 1
        if count:
            self._rebuild_indexes()
            self._persist()
        return count

    def delete(self, predicate, tx_id: int | None = None) -> int:
        count = 0
        for page in self.pages:
            for record in page.records:
                current = record.visible_version(self.pager.current_clock(), tx_id=tx_id)
                if current is not None and predicate(current):
                    ts = self.pager.next_timestamp()
                    record.add_version(current, tx_id=tx_id, commit_ts=ts, deleted=True, committed=True)
                    count += 1
        if count:
            self._rebuild_indexes()
            self._persist()
        return count

    def find_by_index(self, column: str, operator: str, value: object, snapshot_ts: int | None = None, tx_id: int | None = None) -> list[dict[str, object]]:
        index = self.indexes.get(column)
        if index is None:
            return []
        if operator == "=":
            row_ids = index.search(value)
        elif operator in {">", ">=", "<", "<="} and hasattr(index, "range_search"):
            if operator == ">":
                row_ids = index.range_search(low=value, include_low=False)
            elif operator == ">=":
                row_ids = index.range_search(low=value, include_low=True)
            elif operator == "<":
                row_ids = index.range_search(high=value, include_high=False)
            else:
                row_ids = index.range_search(high=value, include_high=True)
        else:
            row_ids = []
        rows = []
        snapshot_ts = snapshot_ts if snapshot_ts is not None else self.pager.current_clock()
        for record in self.iter_records():
            if record.row_id in row_ids:
                values = record.visible_version(snapshot_ts, tx_id=tx_id)
                if values is not None:
                    rows.append(values)
        return rows

    def _validate(self, values: dict[str, object]) -> None:
        expected = {column.name for column in self.columns}
        provided = set(values)
        if expected != provided:
            raise StorageError(f"Expected columns {sorted(expected)}, got {sorted(provided)}")

    def _persist(self) -> None:
        schema = [{"name": column.name, "type": column.type} for column in self.columns]
        self.pager.write_table_data(self.name, {"schema": schema, "storage_format": self.storage_format, "pages": [page.serialize() for page in self.pages]})

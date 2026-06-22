from __future__ import annotations

from dataclasses import dataclass, field

from ..errors import StorageError
from ..index import BTreeIndex, HashIndex
from ..types import Column
from .page import Page
from .pager import Pager
from .record import Record


@dataclass
class Table:
    name: str
    columns: list[Column]
    pager: Pager
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
            self._index_record(record)

    def _index_record(self, record: Record) -> None:
        for column_name, index in self.indexes.items():
            index.insert(record.values.get(column_name), record.row_id)

    def _deindex_record(self, record: Record) -> None:
        for column_name, index in self.indexes.items():
            index.delete(record.values.get(column_name), record.row_id)

    def iter_records(self):
        for page in self.pages:
            for record in page.records:
                yield record

    def insert(self, values: dict[str, object]) -> Record:
        self._validate(values)
        record = Record(values=values, row_id=self.next_row_id)
        self.next_row_id += 1
        if not self.pages or self.pages[-1].is_full():
            self.pages.append(Page(len(self.pages)))
        self.pages[-1].records.append(record)
        self._index_record(record)
        self._persist()
        return record

    def select_all(self) -> list[dict[str, object]]:
        return [record.values for record in self.iter_records()]

    def statistics(self) -> dict[str, object]:
        rows = self.select_all()
        distinct = {
            column.name: len({row.get(column.name) for row in rows})
            for column in self.columns
        }
        return {
            "row_count": len(rows),
            "page_count": len(self.pages),
            "distinct_values": distinct,
        }

    def update(self, predicate, assignments: dict[str, object]) -> int:
        count = 0
        for page in self.pages:
            for record in page.records:
                if predicate(record.values):
                    self._deindex_record(record)
                    record.values.update(assignments)
                    self._index_record(record)
                    count += 1
        if count:
            self._persist()
        return count

    def delete(self, predicate) -> int:
        count = 0
        for page in self.pages:
            retained = []
            for record in page.records:
                if predicate(record.values):
                    self._deindex_record(record)
                    count += 1
                else:
                    retained.append(record)
            page.records = retained
        self.pages = [page for page in self.pages if page.records]
        if count:
            self._persist()
        return count

    def find_by_index(self, column: str, operator: str, value: object) -> list[dict[str, object]]:
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
        for record in self.iter_records():
            if record.row_id in row_ids:
                rows.append(record.values)
        return rows

    def _validate(self, values: dict[str, object]) -> None:
        expected = {column.name for column in self.columns}
        provided = set(values)
        if expected != provided:
            raise StorageError(f"Expected columns {sorted(expected)}, got {sorted(provided)}")

    def _persist(self) -> None:
        schema = [{"name": column.name, "type": column.type} for column in self.columns]
        self.pager.write_table_pages(self.name, schema, self.pages)

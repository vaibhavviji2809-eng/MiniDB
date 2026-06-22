from __future__ import annotations

from dataclasses import dataclass, field
import json

from .record import Record


PAGE_SIZE = 4096


@dataclass
class Page:
    number: int
    records: list[Record] = field(default_factory=list)

    def byte_size(self) -> int:
        payload = json.dumps([record.values for record in self.records], ensure_ascii=False)
        return len(payload.encode("utf-8"))

    def is_full(self) -> bool:
        return self.byte_size() >= PAGE_SIZE

    def serialize(self) -> dict:
        return {
            "number": self.number,
            "records": [
                {"row_id": record.row_id, "values": record.values, "versions": record.versions}
                for record in self.records
            ],
        }

    @classmethod
    def deserialize(cls, data: dict) -> "Page":
        page = cls(data["number"])
        page.records = [
            Record(values=row.get("values", {}), row_id=row.get("row_id"), versions=row.get("versions", []))
            for row in data.get("records", [])
        ]
        return page

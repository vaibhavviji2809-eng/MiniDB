from __future__ import annotations

import json
from pathlib import Path

from ..cache import BufferPoolManager
from .compression import CompressionCodec
from .page import Page


class Pager:
    def __init__(self, path: str | Path, cache_size: int = 64) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = BufferPoolManager(cache_size, policy="clock")
        self.codec = CompressionCodec()
        if not self.path.exists():
            self.path.write_text(json.dumps({"clock": 0, "tables": {}}), encoding="utf-8")

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8") or "{\"clock\":0,\"tables\":{}}")

    def save(self, data: dict) -> None:
        data.setdefault("clock", 0)
        data.setdefault("tables", {})
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def current_clock(self) -> int:
        return int(self.load().get("clock", 0))

    def next_timestamp(self) -> int:
        data = self.load()
        data["clock"] = int(data.get("clock", 0)) + 1
        self.save(data)
        return data["clock"]

    def load_table_pages(self, table_name: str) -> list[Page]:
        table = self.load_table_data(table_name)
        if not table:
            return []
        pages = [Page.deserialize(page) for page in table.get("pages", [])]
        for page in pages:
            self.cache.put((table_name, page.number), page)
        return pages

    def load_table_data(self, table_name: str) -> dict | None:
        data = self.load()
        table = data["tables"].get(table_name)
        if not table:
            return None
        if isinstance(table, dict) and table.get("compressed"):
            return self.codec.unpack(table["payload"])
        return table

    def write_table_pages(self, table_name: str, schema: list[dict], pages: list[Page]) -> None:
        self.write_table_data(
            table_name,
            {
                "schema": schema,
                "storage_format": "row",
                "pages": [page.serialize() for page in pages],
            },
        )

    def write_table_data(self, table_name: str, table_data: dict) -> None:
        data = self.load()
        data["tables"][table_name] = {"compressed": True, "payload": self.codec.pack(table_data)}
        self.save(data)
        for page in table_data.get("pages", []):
            if isinstance(page, dict) and "number" in page:
                self.cache.put((table_name, page["number"]), Page.deserialize(page))

    def drop_table(self, table_name: str) -> None:
        data = self.load()
        data["tables"].pop(table_name, None)
        self.save(data)

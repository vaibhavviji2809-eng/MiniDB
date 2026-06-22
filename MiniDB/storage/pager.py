from __future__ import annotations

import json
from pathlib import Path

from ..cache import LRUCache
from .page import Page


class Pager:
    def __init__(self, path: str | Path, cache_size: int = 64) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = LRUCache(cache_size)
        if not self.path.exists():
            self.path.write_text(json.dumps({"tables": {}}), encoding="utf-8")

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8") or "{\"tables\":{}}")

    def save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_table_pages(self, table_name: str) -> list[Page]:
        data = self.load()
        table = data["tables"].get(table_name)
        if not table:
            return []
        pages = [Page.deserialize(page) for page in table.get("pages", [])]
        for page in pages:
            self.cache.put((table_name, page.number), page)
        return pages

    def write_table_pages(self, table_name: str, schema: list[dict], pages: list[Page]) -> None:
        data = self.load()
        data["tables"][table_name] = {
            "schema": schema,
            "pages": [page.serialize() for page in pages],
        }
        self.save(data)
        for page in pages:
            self.cache.put((table_name, page.number), page)

    def drop_table(self, table_name: str) -> None:
        data = self.load()
        data["tables"].pop(table_name, None)
        self.save(data)


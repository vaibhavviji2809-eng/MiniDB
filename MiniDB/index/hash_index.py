from __future__ import annotations


class HashIndex:
    def __init__(self) -> None:
        self._index: dict[object, set[int]] = {}

    def insert(self, value: object, row_id: int) -> None:
        self._index.setdefault(value, set()).add(row_id)

    def delete(self, value: object, row_id: int) -> None:
        bucket = self._index.get(value)
        if bucket:
            bucket.discard(row_id)
            if not bucket:
                self._index.pop(value, None)

    def search(self, value: object) -> list[int]:
        return sorted(self._index.get(value, set()))


from __future__ import annotations

from bisect import bisect_left, bisect_right


class BTreeIndex:
    def __init__(self) -> None:
        self.keys: list[object] = []
        self.values: list[set[int]] = []

    def insert(self, key: object, row_id: int) -> None:
        pos = bisect_left(self.keys, key)
        if pos < len(self.keys) and self.keys[pos] == key:
            self.values[pos].add(row_id)
        else:
            self.keys.insert(pos, key)
            self.values.insert(pos, {row_id})

    def delete(self, key: object, row_id: int) -> None:
        pos = bisect_left(self.keys, key)
        if pos < len(self.keys) and self.keys[pos] == key:
            self.values[pos].discard(row_id)
            if not self.values[pos]:
                self.keys.pop(pos)
                self.values.pop(pos)

    def search(self, key: object) -> list[int]:
        pos = bisect_left(self.keys, key)
        if pos < len(self.keys) and self.keys[pos] == key:
            return sorted(self.values[pos])
        return []

    def range_search(self, low=None, high=None, include_low=True, include_high=True) -> list[int]:
        result = []
        start = 0 if low is None else bisect_left(self.keys, low) if include_low else bisect_right(self.keys, low)
        for i in range(start, len(self.keys)):
            key = self.keys[i]
            if high is not None:
                if key > high or (not include_high and key == high):
                    break
            result.extend(self.values[i])
        return sorted(result)


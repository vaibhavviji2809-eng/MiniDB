from __future__ import annotations


class BitmapIndex:
    def __init__(self) -> None:
        self.bitmaps: dict[object, set[int]] = {}

    def insert(self, value: object, row_id: int) -> None:
        self.bitmaps.setdefault(value, set()).add(row_id)

    def delete(self, value: object, row_id: int) -> None:
        bitmap = self.bitmaps.get(value)
        if bitmap:
            bitmap.discard(row_id)
            if not bitmap:
                self.bitmaps.pop(value, None)

    def search(self, value: object) -> list[int]:
        return sorted(self.bitmaps.get(value, set()))


from __future__ import annotations

from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity: int = 64) -> None:
        self.capacity = capacity
        self.data: OrderedDict[object, object] = OrderedDict()

    def get(self, key, default=None):
        if key not in self.data:
            return default
        self.data.move_to_end(key)
        return self.data[key]

    def put(self, key, value) -> None:
        self.data[key] = value
        self.data.move_to_end(key)
        if len(self.data) > self.capacity:
            self.data.popitem(last=False)

    def __contains__(self, key) -> bool:
        return key in self.data


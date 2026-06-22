from __future__ import annotations

from collections import OrderedDict, deque


class ClockCache:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.entries: dict[object, tuple[object, bool]] = {}
        self.order: deque[object] = deque()
        self.hand = 0

    def get(self, key, default=None):
        if key not in self.entries:
            return default
        value, _ = self.entries[key]
        self.entries[key] = (value, True)
        return value

    def put(self, key, value) -> None:
        if key not in self.entries and len(self.entries) >= self.capacity:
            self._evict()
        self.entries[key] = (value, True)
        if key not in self.order:
            self.order.append(key)

    def _evict(self):
        if not self.order:
            return
        while self.order:
            key = self.order[0]
            value, ref = self.entries.get(key, (None, False))
            if ref:
                self.entries[key] = (value, False)
                self.order.rotate(-1)
            else:
                self.order.popleft()
                self.entries.pop(key, None)
                return


class LRUKCache:
    def __init__(self, capacity: int, k: int = 2) -> None:
        self.capacity = capacity
        self.k = k
        self.history: dict[object, list[int]] = {}
        self.data: dict[object, object] = {}
        self.clock = 0

    def get(self, key, default=None):
        self.clock += 1
        if key not in self.data:
            return default
        self.history.setdefault(key, []).append(self.clock)
        return self.data[key]

    def put(self, key, value) -> None:
        self.clock += 1
        self.data[key] = value
        self.history.setdefault(key, []).append(self.clock)
        if len(self.data) > self.capacity:
            self._evict()

    def _evict(self):
        victim = min(
            self.data,
            key=lambda key: self.history.get(key, [0])[-self.k] if len(self.history.get(key, [])) >= self.k else -1,
        )
        self.data.pop(victim, None)
        self.history.pop(victim, None)


class ARCCache:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.t1 = OrderedDict()
        self.t2 = OrderedDict()

    def get(self, key, default=None):
        if key in self.t1:
            value = self.t1.pop(key)
            self.t2[key] = value
            return value
        if key in self.t2:
            value = self.t2.pop(key)
            self.t2[key] = value
            return value
        return default

    def put(self, key, value) -> None:
        if key in self.t1:
            self.t1.pop(key, None)
        if key in self.t2:
            self.t2.pop(key, None)
        self.t1[key] = value
        if len(self.t1) + len(self.t2) > self.capacity:
            if self.t1:
                self.t1.popitem(last=False)
            elif self.t2:
                self.t2.popitem(last=False)


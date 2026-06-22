from __future__ import annotations

from .lru import LRUCache
from .policies import ARCCache, ClockCache, LRUKCache


class BufferPoolManager:
    def __init__(self, capacity: int = 64, policy: str = "clock") -> None:
        self.capacity = capacity
        self.policy = policy.lower()
        self.cache = self._build_policy()

    def _build_policy(self):
        if self.policy == "lru":
            return LRUCache(self.capacity)
        if self.policy == "lru-k":
            return LRUKCache(self.capacity)
        if self.policy == "arc":
            return ARCCache(self.capacity)
        return ClockCache(self.capacity)

    def get(self, key, default=None):
        return self.cache.get(key, default)

    def put(self, key, value) -> None:
        self.cache.put(key, value)


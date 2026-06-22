from __future__ import annotations

import threading


class ReadWriteLock:
    def __init__(self) -> None:
        self._lock = threading.RLock()

    def read_lock(self):
        return self._lock

    def write_lock(self):
        return self._lock


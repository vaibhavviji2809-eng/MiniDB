from __future__ import annotations

from pathlib import Path
import shutil


class WALShipper:
    def __init__(self, primary_wal: str | Path, replica_wal: str | Path) -> None:
        self.primary_wal = Path(primary_wal)
        self.replica_wal = Path(replica_wal)

    def ship(self) -> None:
        self.replica_wal.parent.mkdir(parents=True, exist_ok=True)
        if self.primary_wal.exists():
            shutil.copy2(self.primary_wal, self.replica_wal)


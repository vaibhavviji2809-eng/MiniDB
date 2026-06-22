from __future__ import annotations

from dataclasses import dataclass, field

from .wal import WriteAheadLog


@dataclass
class Transaction:
    id: int
    active: bool = True
    operations: list[dict] = field(default_factory=list)


class TransactionManager:
    def __init__(self, wal: WriteAheadLog) -> None:
        self.wal = wal
        self.next_id = 1
        self.active: dict[int, Transaction] = {}

    def begin(self) -> Transaction:
        tx = Transaction(self.next_id)
        self.next_id += 1
        self.active[tx.id] = tx
        self.wal.append({"type": "BEGIN", "tx": tx.id})
        return tx

    def commit(self, tx: Transaction) -> None:
        self.wal.append({"type": "COMMIT", "tx": tx.id, "operations": tx.operations})
        tx.active = False
        self.active.pop(tx.id, None)

    def rollback(self, tx: Transaction) -> None:
        self.wal.append({"type": "ROLLBACK", "tx": tx.id})
        tx.active = False
        self.active.pop(tx.id, None)


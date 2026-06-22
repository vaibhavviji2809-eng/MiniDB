from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Record:
    row_id: int | None = None
    values: dict[str, object] | None = None
    versions: list[dict[str, object]] | None = None

    def __post_init__(self) -> None:
        if self.versions is None:
            self.versions = []
        if self.values is None:
            self.values = {}

    def add_version(self, values: dict[str, object], tx_id: int | None = None, commit_ts: int | None = None, deleted: bool = False, committed: bool = True) -> None:
        self.versions.append(
            {
                "values": values,
                "tx_id": tx_id,
                "commit_ts": commit_ts,
                "deleted": deleted,
                "committed": committed,
            }
        )

    def visible_version(self, snapshot_ts: int, tx_id: int | None = None) -> dict[str, object] | None:
        visible = None
        for version in self.versions:
            if tx_id is not None and version.get("tx_id") == tx_id:
                visible = version
            elif version.get("committed", False) and (version.get("commit_ts") or 0) <= snapshot_ts:
                visible = version
        if visible is None or visible.get("deleted"):
            return None
        return visible.get("values", {})

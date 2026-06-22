from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    type: str


@dataclass(frozen=True)
class Condition:
    left: object
    operator: str
    right: object


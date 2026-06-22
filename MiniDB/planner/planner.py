from __future__ import annotations

from dataclasses import dataclass

from ..parser.ast import (
    BeginStatement,
    CommitStatement,
    CreateTableStatement,
    DeleteStatement,
    DropTableStatement,
    InsertStatement,
    RollbackStatement,
    SelectStatement,
    UpdateStatement,
)


@dataclass
class ScanNode:
    table: str
    use_index: bool = False
    index_column: str | None = None
    index_operator: str | None = None
    index_value: object | None = None


@dataclass
class FilterNode:
    predicate: object


@dataclass
class ProjectNode:
    columns: list[str]


@dataclass
class QueryPlan:
    statement: object
    scan: ScanNode | None = None
    filter: FilterNode | None = None
    project: ProjectNode | None = None


class Planner:
    def plan(self, statement) -> QueryPlan:
        if isinstance(statement, SelectStatement):
            scan = ScanNode(statement.table)
            if self._indexable(statement.where):
                scan.use_index = True
                scan.index_column, scan.index_operator, scan.index_value = self._index_parts(statement.where)
            return QueryPlan(statement=statement, scan=scan, filter=FilterNode(statement.where), project=ProjectNode(statement.columns))
        if isinstance(statement, (InsertStatement, CreateTableStatement, DropTableStatement, UpdateStatement, DeleteStatement, BeginStatement, CommitStatement, RollbackStatement)):
            return QueryPlan(statement=statement)
        raise ValueError(f"Unsupported statement {type(statement)!r}")

    def _indexable(self, where) -> bool:
        return bool(where and hasattr(where, "operator") and where.operator in {"=", ">", ">=", "<", "<="} and where.left.__class__.__name__ == "Identifier" and where.right.__class__.__name__ == "Literal")

    def _index_parts(self, where):
        return where.left.name, where.operator, where.right.value


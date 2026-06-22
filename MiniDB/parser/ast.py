from __future__ import annotations

from dataclasses import dataclass, field

from ..types import Column


class Statement:
    pass


class Expression:
    pass


@dataclass
class Identifier(Expression):
    name: str


@dataclass
class Literal(Expression):
    value: object


@dataclass
class BinaryExpression(Expression):
    left: Expression
    operator: str
    right: Expression


@dataclass
class TableRef:
    name: str
    alias: str | None = None


@dataclass
class JoinClause:
    join_type: str
    table: TableRef
    condition: Expression | None = None


@dataclass
class SelectStatement(Statement):
    columns: list[str]
    table: TableRef
    joins: list[JoinClause] = field(default_factory=list)
    where: Expression | None = None


@dataclass
class InsertStatement(Statement):
    table: str
    values: list[object]


@dataclass
class CreateTableStatement(Statement):
    table: str
    columns: list[Column] = field(default_factory=list)
    storage_format: str = "row"


@dataclass
class DropTableStatement(Statement):
    table: str


@dataclass
class UpdateStatement(Statement):
    table: str
    assignments: dict[str, Expression]
    where: Expression | None = None


@dataclass
class DeleteStatement(Statement):
    table: str
    where: Expression | None = None


@dataclass
class BeginStatement(Statement):
    pass


@dataclass
class CommitStatement(Statement):
    pass


@dataclass
class RollbackStatement(Statement):
    pass


@dataclass
class ExplainStatement(Statement):
    statement: Statement
    analyze: bool = False

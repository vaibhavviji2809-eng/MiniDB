from __future__ import annotations

from dataclasses import dataclass

from ..parser.ast import (
    BeginStatement,
    BinaryExpression,
    CommitStatement,
    CreateTableStatement,
    DeleteStatement,
    DropTableStatement,
    Identifier,
    InsertStatement,
    Literal,
    RollbackStatement,
    SelectStatement,
    UpdateStatement,
)
from ..storage import Pager, Table
from ..transaction import TransactionManager, WriteAheadLog


@dataclass
class Result:
    columns: list[str]
    rows: list[dict[str, object]]


class Executor:
    def __init__(self, database_path: str) -> None:
        self.pager = Pager(database_path)
        self.wal = WriteAheadLog(str(self.pager.path.with_suffix(".wal")))
        self.transactions = TransactionManager(self.wal)
        self.active_transaction = None
        self._transaction_snapshot: str | None = None

    def execute(self, plan):
        statement = plan.statement
        if isinstance(statement, CreateTableStatement):
            return self._create_table(statement)
        if isinstance(statement, InsertStatement):
            return self._insert(statement)
        if isinstance(statement, SelectStatement):
            return self._select(statement, plan)
        if isinstance(statement, UpdateStatement):
            return self._update(statement)
        if isinstance(statement, DeleteStatement):
            return self._delete(statement)
        if isinstance(statement, DropTableStatement):
            self.pager.drop_table(statement.table)
            self._record_operation({"type": "DROP_TABLE", "table": statement.table})
            return Result([], [])
        if isinstance(statement, BeginStatement):
            self.active_transaction = self.transactions.begin()
            self._transaction_snapshot = self.pager.path.read_text(encoding="utf-8")
            return Result([], [])
        if isinstance(statement, CommitStatement):
            if self.active_transaction:
                self.transactions.commit(self.active_transaction)
                self.active_transaction = None
                self._transaction_snapshot = None
            return Result([], [])
        if isinstance(statement, RollbackStatement):
            if self.active_transaction:
                self.transactions.rollback(self.active_transaction)
                self.active_transaction = None
                if self._transaction_snapshot is not None:
                    self.pager.path.write_text(self._transaction_snapshot, encoding="utf-8")
                    self._transaction_snapshot = None
            return Result([], [])
        raise ValueError(f"Unsupported statement {type(statement)!r}")

    def _load_table(self, name: str) -> Table:
        data = self.pager.load()
        table_data = data["tables"].get(name)
        if not table_data:
            raise ValueError(f"Table {name} does not exist")
        columns = [self._column_from_dict(column) for column in table_data["schema"]]
        return Table(name=name, columns=columns, pager=self.pager)

    def _create_table(self, statement: CreateTableStatement):
        table = Table(name=statement.table, columns=statement.columns, pager=self.pager)
        table._persist()
        self._record_operation({"type": "CREATE_TABLE", "table": statement.table})
        return Result([], [])

    def _insert(self, statement: InsertStatement):
        table = self._load_table(statement.table)
        row = {column.name: value for column, value in zip(table.columns, statement.values)}
        table.insert(row)
        self._record_operation({"type": "INSERT", "table": statement.table, "row": row})
        return Result([], [])

    def _select(self, statement: SelectStatement, plan):
        table = self._load_table(statement.table)
        rows = []
        if plan.scan and plan.scan.use_index and plan.scan.index_column:
            rows = table.find_by_index(plan.scan.index_column, plan.scan.index_operator, plan.scan.index_value)
        else:
            rows = table.select_all()
        if statement.where is not None:
            rows = [row for row in rows if self._evaluate(statement.where, row)]
        if statement.columns != ["*"]:
            rows = [{col: row.get(col) for col in statement.columns} for row in rows]
            columns = statement.columns
        else:
            columns = list(rows[0].keys()) if rows else [column.name for column in table.columns]
        return Result(columns, rows)

    def _update(self, statement: UpdateStatement):
        table = self._load_table(statement.table)
        assignments = {k: self._resolve(v, {}) for k, v in statement.assignments.items()}
        count = table.update(lambda row: statement.where is None or self._evaluate(statement.where, row), assignments)
        self._record_operation({"type": "UPDATE", "table": statement.table, "assignments": assignments, "count": count})
        return Result(["updated"], [{"updated": count}])

    def _delete(self, statement: DeleteStatement):
        table = self._load_table(statement.table)
        count = table.delete(lambda row: statement.where is None or self._evaluate(statement.where, row))
        self._record_operation({"type": "DELETE", "table": statement.table, "count": count})
        return Result(["deleted"], [{"deleted": count}])

    def _evaluate(self, expr, row):
        if isinstance(expr, Literal):
            return expr.value
        if isinstance(expr, Identifier):
            return row.get(expr.name)
        if isinstance(expr, BinaryExpression):
            left = self._evaluate(expr.left, row)
            right = self._evaluate(expr.right, row)
            if expr.operator == "=":
                return left == right
            if expr.operator == "!=":
                return left != right
            if expr.operator == ">":
                return left > right
            if expr.operator == ">=":
                return left >= right
            if expr.operator == "<":
                return left < right
            if expr.operator == "<=":
                return left <= right
            if expr.operator == "AND":
                return bool(left) and bool(right)
            if expr.operator == "OR":
                return bool(left) or bool(right)
        return expr

    def _resolve(self, expr, row):
        return self._evaluate(expr, row)

    def _column_from_dict(self, data):
        from ..types import Column

        return Column(data["name"], data["type"])

    def _record_operation(self, operation: dict) -> None:
        if self.active_transaction is not None:
            self.active_transaction.operations.append(operation)

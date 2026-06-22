from __future__ import annotations

from dataclasses import dataclass
import time

from ..parser.ast import (
    BeginStatement,
    BinaryExpression,
    CommitStatement,
    CreateTableStatement,
    DeleteStatement,
    DropTableStatement,
    ExplainStatement,
    Identifier,
    InsertStatement,
    Literal,
    RollbackStatement,
    SelectStatement,
    TableRef,
    UpdateStatement,
)
from .vectorized import vectorized_filter, vectorized_project
from ..storage import ColumnTable, Pager, Table
from ..statistics import StatisticsEngine
from ..transaction import ReaderWriterLock, TransactionManager, WriteAheadLog


@dataclass
class Result:
    columns: list[str]
    rows: list[dict[str, object]]


class Executor:
    def __init__(self, database_path: str) -> None:
        self.pager = Pager(database_path)
        self.wal = WriteAheadLog(str(self.pager.path.with_suffix(".wal")))
        self.transactions = TransactionManager(self.wal)
        self.lock = ReaderWriterLock()
        self.stats = StatisticsEngine()
        self.active_transaction = None
        self._transaction_snapshot: str | None = None

    def table_statistics(self, table_name: str) -> dict[str, object]:
        table = self.describe_table(table_name)
        rows = table.select_all()
        stats = self.stats.table_statistics(rows)
        return {
            "row_count": stats.row_count,
            "distinct_values": stats.distinct_count,
            "null_count": stats.null_count,
            "histogram": stats.histogram,
        }

    def describe_table(self, table_name: str):
        table_data = self.pager.load_table_data(table_name)
        if not table_data:
            raise ValueError(f"Table {table_name} does not exist")
        columns = [self._column_from_dict(column) for column in table_data["schema"]]
        storage_format = table_data.get("storage_format", "row")
        if storage_format == "column":
            return ColumnTable(name=table_name, columns=columns, pager=self.pager)
        return Table(name=table_name, columns=columns, pager=self.pager, storage_format=storage_format)

    def execute(self, plan):
        statement = plan.statement
        if isinstance(statement, ExplainStatement):
            return self._explain(plan)
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
            with self.lock.write_lock():
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

    def _explain(self, plan):
        if plan.statement.analyze:
            start = time.perf_counter()
            with self.lock.read_lock():
                self._execute_plan(plan.physical_plan, snapshot_ts=self._snapshot_ts())
            elapsed = (time.perf_counter() - start) * 1000.0
            lines = plan.explain().splitlines()
            lines.append(f"Execution Time: {elapsed:.3f} ms")
            return Result(["explain"], [{"explain": "\n".join(lines)}])
        return Result(["explain"], [{"explain": plan.explain()}])

    def _load_table(self, name: str):
        return self.describe_table(name)

    def _create_table(self, statement: CreateTableStatement):
        with self.lock.write_lock():
            if statement.storage_format == "column":
                table = ColumnTable(name=statement.table, columns=statement.columns, pager=self.pager)
                table._persist()
            else:
                table = Table(name=statement.table, columns=statement.columns, pager=self.pager, storage_format=statement.storage_format)
                table._persist()
        self._record_operation({"type": "CREATE_TABLE", "table": statement.table, "storage_format": statement.storage_format})
        return Result([], [])

    def _insert(self, statement: InsertStatement):
        with self.lock.write_lock():
            table = self._load_table(statement.table)
            row = {column.name: value for column, value in zip(table.columns, statement.values)}
            table.insert(row, tx_id=self._tx_id())
        self._record_operation({"type": "INSERT", "table": statement.table, "row": row})
        return Result([], [])

    def _select(self, statement: SelectStatement, plan):
        with self.lock.read_lock():
            rows = self._execute_plan(plan.physical_plan, snapshot_ts=self._snapshot_ts())
        if statement.columns != ["*"]:
            rows = [self._project_row(row, statement.columns) for row in rows]
            columns = statement.columns
        else:
            columns = list(rows[0].keys()) if rows else []
        return Result(columns, rows)

    def _update(self, statement: UpdateStatement):
        with self.lock.write_lock():
            table = self._load_table(statement.table)
            assignments = {k: self._resolve(v, {}) for k, v in statement.assignments.items()}
            count = table.update(lambda row: statement.where is None or self._evaluate(statement.where, row), assignments, tx_id=self._tx_id())
        self._record_operation({"type": "UPDATE", "table": statement.table, "assignments": assignments, "count": count})
        return Result(["updated"], [{"updated": count}])

    def _delete(self, statement: DeleteStatement):
        with self.lock.write_lock():
            table = self._load_table(statement.table)
            count = table.delete(lambda row: statement.where is None or self._evaluate(statement.where, row), tx_id=self._tx_id())
        self._record_operation({"type": "DELETE", "table": statement.table, "count": count})
        return Result(["deleted"], [{"deleted": count}])

    def _execute_plan(self, node, snapshot_ts: int | None = None) -> list[dict[str, object]]:
        kind = node.kind
        if kind in {"TableScan", "Scan"}:
            table = self._load_table(node.props["table"])
            rows = table.select_all(snapshot_ts=snapshot_ts, tx_id=self._tx_id())
            return [self._augment_row(node.props["table"], node.props.get("alias"), row) for row in rows]
        if kind == "IndexScan":
            table = self._load_table(node.props["table"])
            rows = table.find_by_index(node.props["column"], node.props["operator"], node.props["value"], snapshot_ts=snapshot_ts, tx_id=self._tx_id())
            return [self._augment_row(node.props["table"], None, row) for row in rows]
        if kind == "Filter":
            rows = self._execute_plan(node.children[0], snapshot_ts)
            return vectorized_filter(rows, lambda row: self._evaluate(node.props["predicate"], row))
        if kind == "Project":
            rows = self._execute_plan(node.children[0], snapshot_ts)
            return vectorized_project(rows, node.props["columns"])
        if kind in {"NestedLoopJoin", "HashJoin", "MergeJoin", "IndexJoin"}:
            left_rows = self._execute_plan(node.children[0], snapshot_ts)
            right_rows = self._execute_plan(node.children[1], snapshot_ts)
            return self._join(kind, left_rows, right_rows, node.props.get("condition"))
        return []

    def _join(self, kind: str, left_rows: list[dict[str, object]], right_rows: list[dict[str, object]], condition):
        if kind == "HashJoin" and isinstance(condition, BinaryExpression) and condition.operator == "=":
            left_key, right_key = self._join_keys(condition)
            buckets: dict[object, list[dict[str, object]]] = {}
            for row in right_rows:
                buckets.setdefault(row.get(right_key), []).append(row)
            results = []
            for left in left_rows:
                for right in buckets.get(left.get(left_key), []):
                    merged = {**left, **right}
                    if self._evaluate(condition, merged):
                        results.append(merged)
            return results
        if kind == "MergeJoin" and isinstance(condition, BinaryExpression) and condition.operator == "=":
            left_key, right_key = self._join_keys(condition)
            left_sorted = sorted(left_rows, key=lambda row: row.get(left_key))
            right_sorted = sorted(right_rows, key=lambda row: row.get(right_key))
            i = j = 0
            results = []
            while i < len(left_sorted) and j < len(right_sorted):
                lv = left_sorted[i].get(left_key)
                rv = right_sorted[j].get(right_key)
                if lv == rv:
                    k = j
                    while k < len(right_sorted) and right_sorted[k].get(right_key) == rv:
                        merged = {**left_sorted[i], **right_sorted[k]}
                        if self._evaluate(condition, merged):
                            results.append(merged)
                        k += 1
                    i += 1
                elif lv < rv:
                    i += 1
                else:
                    j += 1
            return results
        if kind == "IndexJoin" and isinstance(condition, BinaryExpression) and condition.operator == "=":
            left_key, right_key = self._join_keys(condition)
            index = {}
            for row in right_rows:
                index.setdefault(row.get(right_key), []).append(row)
            results = []
            for left in left_rows:
                for right in index.get(left.get(left_key), []):
                    merged = {**left, **right}
                    if self._evaluate(condition, merged):
                        results.append(merged)
            return results
        results = []
        for left in left_rows:
            for right in right_rows:
                merged = {**left, **right}
                if condition is None or self._evaluate(condition, merged):
                    results.append(merged)
        return results

    def _join_keys(self, condition: BinaryExpression) -> tuple[str, str]:
        left = condition.left.name if isinstance(condition.left, Identifier) else ""
        right = condition.right.name if isinstance(condition.right, Identifier) else ""
        return left, right

    def _project_row(self, row: dict[str, object], columns: list[str]) -> dict[str, object]:
        return {column: row.get(column) for column in columns}

    def _augment_row(self, table_name: str, alias: str | None, row: dict[str, object]) -> dict[str, object]:
        augmented = dict(row)
        prefix = alias or table_name
        for key, value in row.items():
            qualified = f"{table_name}.{key}"
            augmented[qualified] = value
            if alias:
                augmented[f"{alias}.{key}"] = value
            augmented.setdefault(key, value)
        augmented["_source_table"] = prefix
        return augmented

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

    def _tx_id(self) -> int | None:
        return self.active_transaction.id if self.active_transaction else None

    def _snapshot_ts(self) -> int:
        if self.active_transaction is not None:
            return self.active_transaction.start_ts
        return self.pager.current_clock()

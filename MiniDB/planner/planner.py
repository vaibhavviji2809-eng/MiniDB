from __future__ import annotations

from dataclasses import dataclass, field
from math import log2
from typing import Any

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


@dataclass
class PlanNode:
    kind: str
    children: list["PlanNode"] = field(default_factory=list)
    props: dict[str, Any] = field(default_factory=dict)

    def explain_lines(self, indent: int = 0) -> list[str]:
        pad = "  " * indent
        details = ", ".join(f"{k}={v}" for k, v in self.props.items() if v is not None)
        line = f"{pad}{self.kind}" + (f" [{details}]" if details else "")
        lines = [line]
        for child in self.children:
            lines.extend(child.explain_lines(indent + 1))
        return lines


@dataclass
class CostEstimate:
    rows: float
    cpu: float
    io: float

    @property
    def total(self) -> float:
        return self.rows + self.cpu + self.io


class CostModel:
    def estimate_table_scan(self, stats: dict[str, Any]) -> CostEstimate:
        rows = max(float(stats.get("row_count", 0)), 1.0)
        return CostEstimate(rows=rows, cpu=rows * 0.15, io=rows * 0.75)

    def estimate_index_scan(self, stats: dict[str, Any], selectivity: float = 0.1) -> CostEstimate:
        rows = max(float(stats.get("row_count", 0)), 1.0)
        matched = max(rows * selectivity, 1.0)
        return CostEstimate(rows=matched, cpu=log2(rows + 1.0) * 0.5, io=matched * 0.25)

    def estimate_nested_loop(self, left: float, right: float) -> CostEstimate:
        rows = left * right
        return CostEstimate(rows=rows, cpu=rows * 0.05, io=rows * 0.02)

    def estimate_hash_join(self, left: float, right: float) -> CostEstimate:
        rows = left + right
        return CostEstimate(rows=rows, cpu=rows * 0.4, io=rows * 0.15)

    def estimate_merge_join(self, left: float, right: float) -> CostEstimate:
        sort_cost = left * log2(left + 1.0) + right * log2(right + 1.0)
        rows = left + right
        return CostEstimate(rows=rows, cpu=sort_cost * 0.1, io=rows * 0.12)

    def estimate_index_join(self, left: float, right: float) -> CostEstimate:
        rows = left + right * 0.2
        return CostEstimate(rows=rows, cpu=rows * 0.3, io=rows * 0.1)

    def choose_best_plan(self, candidates: list[tuple[PlanNode, CostEstimate]]) -> tuple[PlanNode, CostEstimate]:
        if not candidates:
            raise ValueError("No candidate plans available")
        return min(candidates, key=lambda item: item[1].total)


@dataclass
class QueryPlan:
    statement: object
    logical_plan: PlanNode | None = None
    physical_plan: PlanNode | None = None
    cost: CostEstimate | None = None

    def explain(self) -> str:
        if self.physical_plan is None:
            return "Empty plan"
        return "\n".join(self.physical_plan.explain_lines())


class Planner:
    def __init__(self, cost_model: CostModel | None = None) -> None:
        self.cost_model = cost_model or CostModel()

    def plan(self, statement, catalog=None) -> QueryPlan:
        if isinstance(statement, ExplainStatement):
            inner = self.plan(statement.statement, catalog)
            return QueryPlan(statement=statement, logical_plan=inner.logical_plan, physical_plan=inner.physical_plan, cost=inner.cost)
        if isinstance(statement, SelectStatement):
            logical = self._build_logical_select(statement)
            physical, cost = self._build_physical_select(statement, catalog)
            return QueryPlan(statement=statement, logical_plan=logical, physical_plan=physical, cost=cost)
        if isinstance(statement, (InsertStatement, CreateTableStatement, DropTableStatement, UpdateStatement, DeleteStatement, BeginStatement, CommitStatement, RollbackStatement)):
            node = PlanNode(type(statement).__name__.removesuffix("Statement").upper(), props=self._statement_props(statement))
            return QueryPlan(statement=statement, logical_plan=node, physical_plan=node, cost=CostEstimate(1.0, 1.0, 0.5))
        raise ValueError(f"Unsupported statement {type(statement)!r}")

    def _build_logical_select(self, statement: SelectStatement) -> PlanNode:
        root = PlanNode("Select", props={"columns": statement.columns})
        scan = PlanNode("Scan", props={"table": self._resolved_name(statement.table), "alias": statement.table.alias})
        current = scan
        for join in statement.joins:
            join_node = PlanNode(
                "Join",
                children=[current, PlanNode("Scan", props={"table": self._resolved_name(join.table), "alias": join.table.alias})],
                props={"join_type": join.join_type, "condition": join.condition},
            )
            current = join_node
        if statement.where is not None:
            current = PlanNode("Filter", children=[current], props={"predicate": statement.where})
        root.children = [current]
        return root

    def _build_physical_select(self, statement: SelectStatement, catalog=None) -> tuple[PlanNode, CostEstimate]:
        source_plan, source_cost, left_rows = self._access_path(statement.table, statement.where, catalog)
        current = source_plan
        current_cost = source_cost
        current_rows = left_rows
        for join in statement.joins:
            right_plan, right_cost, right_rows = self._access_path(join.table, None, catalog)
            join_plan, join_cost = self._best_join_plan(current, right_plan, current_rows, right_rows, join.condition, catalog)
            current = join_plan
            current_cost = CostEstimate(
                rows=current_cost.rows + right_cost.rows + join_cost.rows,
                cpu=current_cost.cpu + right_cost.cpu + join_cost.cpu,
                io=current_cost.io + right_cost.io + join_cost.io,
            )
            current_rows = max(current_rows, right_rows)
        if statement.where is not None and not self._is_indexable(statement.where):
            current = PlanNode("Filter", children=[current], props={"predicate": statement.where})
            current_cost = CostEstimate(current_cost.rows, current_cost.cpu + current_rows * 0.1, current_cost.io)
        if statement.columns != ["*"]:
            current = PlanNode("Project", children=[current], props={"columns": statement.columns})
            current_cost = CostEstimate(current_cost.rows, current_cost.cpu + len(statement.columns) * 0.05, current_cost.io)
        return current, current_cost

    def _best_join_plan(self, left_plan: PlanNode, right_plan: PlanNode, left_rows: float, right_rows: float, condition, catalog=None) -> tuple[PlanNode, CostEstimate]:
        candidates: list[tuple[PlanNode, CostEstimate]] = []
        candidates.append((PlanNode("NestedLoopJoin", children=[left_plan, right_plan], props={"condition": condition}), self.cost_model.estimate_nested_loop(left_rows, right_rows)))
        candidates.append((PlanNode("HashJoin", children=[left_plan, right_plan], props={"condition": condition}), self.cost_model.estimate_hash_join(left_rows, right_rows)))
        candidates.append((PlanNode("MergeJoin", children=[left_plan, right_plan], props={"condition": condition}), self.cost_model.estimate_merge_join(left_rows, right_rows)))
        if self._join_has_index(condition, catalog):
            candidates.append((PlanNode("IndexJoin", children=[left_plan, right_plan], props={"condition": condition}), self.cost_model.estimate_index_join(left_rows, right_rows)))
        return self.cost_model.choose_best_plan(candidates)

    def _access_path(self, table_ref: TableRef, where, catalog=None) -> tuple[PlanNode, CostEstimate, float]:
        stats = self._table_stats(table_ref, catalog)
        table_name = self._resolved_name(table_ref)
        scan_plan = PlanNode("TableScan", props={"table": table_name, "alias": table_ref.alias})
        scan_cost = self.cost_model.estimate_table_scan(stats)
        candidates: list[tuple[PlanNode, CostEstimate, float]] = [(scan_plan, scan_cost, float(stats.get("row_count", 0)))]
        if self._is_indexable(where):
            index_plan = PlanNode("IndexScan", props={"table": table_name, "column": where.left.name, "operator": where.operator, "value": where.right.value})
            index_cost = self.cost_model.estimate_index_scan(stats, self._selectivity(stats, where))
            candidates.append((index_plan, index_cost, max(float(stats.get("row_count", 0)) * self._selectivity(stats, where), 1.0)))
        plan, cost, rows = min(candidates, key=lambda item: item[1].total)
        return plan, cost, rows

    def _table_stats(self, table_ref: TableRef, catalog=None) -> dict[str, Any]:
        if catalog is None:
            return {"row_count": 1000, "distinct_values": {}}
        table_name = self._resolved_name(table_ref)
        if hasattr(catalog, "table_statistics"):
            return catalog.table_statistics(table_name)
        if hasattr(catalog, "describe_table"):
            table = catalog.describe_table(table_name)
            if hasattr(table, "statistics"):
                return table.statistics()
        return {"row_count": 1000, "distinct_values": {}}

    def _selectivity(self, stats: dict[str, Any], where) -> float:
        if not self._is_indexable(where):
            return 1.0
        distinct = stats.get("distinct_values", {}).get(where.left.name, 10) or 10
        return max(1.0 / float(distinct), 0.01)

    def _is_indexable(self, where) -> bool:
        return bool(where and isinstance(where, BinaryExpression) and where.operator in {"=", ">", ">=", "<", "<="} and isinstance(where.left, Identifier) and isinstance(where.right, Literal))

    def _join_has_index(self, condition, catalog=None) -> bool:
        return self._is_indexable(condition)

    def _resolved_name(self, table_ref: TableRef) -> str:
        return table_ref.name

    def _statement_props(self, statement) -> dict[str, Any]:
        if isinstance(statement, CreateTableStatement):
            return {"table": statement.table, "storage_format": statement.storage_format}
        if isinstance(statement, InsertStatement):
            return {"table": statement.table}
        if isinstance(statement, DropTableStatement):
            return {"table": statement.table}
        if isinstance(statement, (UpdateStatement, DeleteStatement)):
            return {"table": statement.table}
        return {}

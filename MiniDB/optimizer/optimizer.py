from __future__ import annotations

from ..parser.ast import BinaryExpression, ExplainStatement, Literal, SelectStatement
from ..planner.planner import QueryPlan


class Optimizer:
    def optimize(self, plan: QueryPlan) -> QueryPlan:
        statement = plan.statement
        if isinstance(statement, ExplainStatement):
            statement = statement.statement
        if isinstance(statement, SelectStatement):
            if statement.where is not None:
                statement.where = self._fold(statement.where)
            for join in statement.joins:
                if join.condition is not None:
                    join.condition = self._fold(join.condition)
        return plan

    def _fold(self, expr):
        if isinstance(expr, BinaryExpression):
            left = self._fold(expr.left)
            right = self._fold(expr.right)
            if isinstance(left, Literal) and isinstance(right, Literal):
                return Literal(self._evaluate(left.value, expr.operator, right.value))
            return BinaryExpression(left, expr.operator, right)
        return expr

    def _evaluate(self, left, operator, right):
        if operator == "=":
            return left == right
        if operator == "!=":
            return left != right
        if operator == ">":
            return left > right
        if operator == ">=":
            return left >= right
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == "AND":
            return bool(left) and bool(right)
        if operator == "OR":
            return bool(left) or bool(right)
        return False

    def _is_indexable(self, expr):
        return bool(expr and hasattr(expr, "operator") and expr.operator in {"=", ">", ">=", "<", "<="} and expr.left.__class__.__name__ == "Identifier" and expr.right.__class__.__name__ == "Literal")

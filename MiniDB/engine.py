from __future__ import annotations

from pathlib import Path

from .execution import Executor
from .optimizer import Optimizer
from .parser import Parser
from .planner import Planner


class DatabaseEngine:
    def __init__(self, database_path: str | None = None) -> None:
        self.database_path = database_path or str(Path("work") / "database.db")
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self.parser = Parser()
        self.planner = Planner()
        self.optimizer = Optimizer()
        self.executor = Executor(self.database_path)

    def execute(self, sql: str):
        statement = self.parser.parse(sql)
        plan = self.planner.plan(statement)
        plan = self.optimizer.optimize(plan)
        return self.executor.execute(plan)


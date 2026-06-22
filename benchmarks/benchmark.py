from __future__ import annotations

import argparse
import statistics
import sqlite3
import tempfile
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from MiniDB.engine import DatabaseEngine
from MiniDB.planner import PlanNode


def format_seconds(value: float) -> str:
    return f"{value * 1000:.3f} ms"


def print_table(title: str, rows: list[tuple[str, str]]):
    print(title)
    width = max((len(name) for name, _ in rows), default=0)
    for name, value in rows:
        print(f"  {name.ljust(width)}  {value}")
    print()



def time_block(func, repeat: int = 1):
    durations = []
    for _ in range(repeat):
        start = time.perf_counter()
        func()
        durations.append(time.perf_counter() - start)
    return statistics.mean(durations)


def benchmark_minidb(rows: int):
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "database.db"
        engine = DatabaseEngine(str(db_path))
        engine.execute("CREATE TABLE users (id INT, name STRING, age INT);")

        def insert():
            for i in range(rows):
                engine.execute(f'INSERT INTO users VALUES ({i},"User{i}",{20 + (i % 10)});')

        insert_time = time_block(insert)
        lookup_time = time_block(lambda: engine.execute("SELECT name FROM users WHERE age > 25;"))
        return {"insert_seconds": insert_time, "lookup_seconds": lookup_time}


def benchmark_row_vs_column(rows: int):
    with tempfile.TemporaryDirectory() as tmp:
        row_engine = DatabaseEngine(str(Path(tmp) / "row.db"))
        col_engine = DatabaseEngine(str(Path(tmp) / "col.db"))
        row_engine.execute("CREATE TABLE users (id INT, name STRING, age INT);")
        col_engine.execute("CREATE TABLE users (id INT, name STRING, age INT) STORAGE COLUMN;")

        def load(engine):
            for i in range(rows):
                engine.execute(f'INSERT INTO users VALUES ({i},"User{i}",{20 + (i % 10)});')

        row_insert = time_block(lambda: load(row_engine))
        col_insert = time_block(lambda: load(col_engine))
        row_select = time_block(lambda: row_engine.execute("SELECT name FROM users WHERE age > 25;"))
        col_select = time_block(lambda: col_engine.execute("SELECT name FROM users WHERE age > 25;"))
        return {
            "row_store": {"insert_seconds": row_insert, "lookup_seconds": row_select},
            "column_store": {"insert_seconds": col_insert, "lookup_seconds": col_select},
        }


def benchmark_join_algorithms(rows: int):
    with tempfile.TemporaryDirectory() as tmp:
        engine = DatabaseEngine(str(Path(tmp) / "joins.db"))
        engine.execute("CREATE TABLE users (id INT, name STRING, age INT);")
        engine.execute("CREATE TABLE orders (id INT, user_id INT, total INT);")
        for i in range(rows):
            engine.execute(f'INSERT INTO users VALUES ({i},"User{i}",{20 + (i % 10)});')
            engine.execute(f'INSERT INTO orders VALUES ({i},{i},{100 + i});')
        left = PlanNode("TableScan", props={"table": "users"})
        right = PlanNode("TableScan", props={"table": "orders"})
        executor = engine.executor
        condition = engine.parser.parse("SELECT users.id FROM users JOIN orders ON users.id = orders.user_id;").joins[0].condition
        timings = {}
        for kind in ["NestedLoopJoin", "HashJoin", "MergeJoin"]:
            node = PlanNode(kind, children=[left, right], props={"condition": condition})
            timings[kind] = time_block(lambda: executor._execute_plan(node))
        return timings


def benchmark_sqlite(rows: int):
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "sqlite.db"
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE users (id INT, name TEXT, age INT)")

        def insert():
            cur.executemany(
                "INSERT INTO users VALUES (?, ?, ?)",
                [(i, f"User{i}", 20 + (i % 10)) for i in range(rows)],
            )
            conn.commit()

        insert_time = time_block(insert)
        lookup_time = time_block(lambda: list(cur.execute("SELECT name FROM users WHERE age > 25")))
        conn.close()
        return {"insert_seconds": insert_time, "lookup_seconds": lookup_time}


def main():
    parser = argparse.ArgumentParser(description="Benchmark MiniDB against SQLite.")
    parser.add_argument("--rows", type=int, default=1000)
    args = parser.parse_args()

    minidb = benchmark_minidb(args.rows)
    row_vs_column = benchmark_row_vs_column(args.rows)
    joins = benchmark_join_algorithms(min(args.rows, 200))
    sqlite = benchmark_sqlite(args.rows)

    print_table(
        "MiniDB",
        [
            ("Insert", format_seconds(minidb["insert_seconds"])),
            ("Lookup", format_seconds(minidb["lookup_seconds"])),
        ],
    )
    print_table(
        "Row Store",
        [
            ("Insert", format_seconds(row_vs_column["row_store"]["insert_seconds"])),
            ("Lookup", format_seconds(row_vs_column["row_store"]["lookup_seconds"])),
        ],
    )
    print_table(
        "Column Store",
        [
            ("Insert", format_seconds(row_vs_column["column_store"]["insert_seconds"])),
            ("Lookup", format_seconds(row_vs_column["column_store"]["lookup_seconds"])),
        ],
    )
    print_table(
        "Join Algorithms",
        [(name.replace("Join", " Join"), format_seconds(value)) for name, value in joins.items()],
    )
    print_table(
        "SQLite",
        [
            ("Insert", format_seconds(sqlite["insert_seconds"])),
            ("Lookup", format_seconds(sqlite["lookup_seconds"])),
        ],
    )


if __name__ == "__main__":
    main()

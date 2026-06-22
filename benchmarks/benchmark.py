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

    print("MiniDB:", benchmark_minidb(args.rows))
    print("SQLite:", benchmark_sqlite(args.rows))


if __name__ == "__main__":
    main()

from __future__ import annotations

from ..engine import DatabaseEngine


def main():
    engine = DatabaseEngine()
    print("MiniDB ready. Type SQL, or 'exit'.")
    while True:
        try:
            sql = input("MiniDB> ").strip()
        except EOFError:
            break
        if not sql:
            continue
        if sql.lower() in {"exit", "quit"}:
            break
        if not sql.endswith(";"):
            sql += ";"
        try:
            result = engine.execute(sql)
            if result.rows:
                for row in result.rows:
                    print(row)
            else:
                print("OK")
        except Exception as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()


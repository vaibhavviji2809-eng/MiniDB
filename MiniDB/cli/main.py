from __future__ import annotations

from ..engine import DatabaseEngine


def _print_result(result):
    if not result.rows:
        print("OK")
        return
    if result.columns == ["explain"] and "explain" in result.rows[0]:
        print(result.rows[0]["explain"])
        return
    columns = result.columns or sorted(result.rows[0].keys())
    widths = {column: max(len(column), *(len(str(row.get(column, ""))) for row in result.rows)) for column in columns}
    header = " | ".join(column.ljust(widths[column]) for column in columns)
    separator = "-+-".join("-" * widths[column] for column in columns)
    print(header)
    print(separator)
    for row in result.rows:
        print(" | ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))


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
            _print_result(result)
        except Exception as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()

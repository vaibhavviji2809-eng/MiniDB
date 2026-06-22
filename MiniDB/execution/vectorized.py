from __future__ import annotations

from itertools import islice


def batch_rows(rows: list[dict[str, object]], batch_size: int = 1024):
    it = iter(rows)
    while True:
        batch = list(islice(it, batch_size))
        if not batch:
            break
        yield batch


def vectorized_filter(rows: list[dict[str, object]], predicate):
    filtered = []
    for batch in batch_rows(rows):
        filtered.extend(row for row in batch if predicate(row))
    return filtered


def vectorized_project(rows: list[dict[str, object]], columns: list[str]):
    projected = []
    for batch in batch_rows(rows):
        projected.extend({column: row.get(column) for column in columns} for row in batch)
    return projected


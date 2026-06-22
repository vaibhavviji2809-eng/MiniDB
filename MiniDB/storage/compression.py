from __future__ import annotations

import base64
import json
import zlib
from itertools import groupby
from typing import Any


class CompressionCodec:
    def dictionary_encode(self, rows: list[dict[str, object]]) -> dict[str, Any]:
        dictionaries: dict[str, dict[object, int]] = {}
        encoded_rows: list[dict[str, int]] = []
        for row in rows:
            encoded_row: dict[str, int] = {}
            for column, value in row.items():
                dictionary = dictionaries.setdefault(column, {})
                if value not in dictionary:
                    dictionary[value] = len(dictionary)
                encoded_row[column] = dictionary[value]
            encoded_rows.append(encoded_row)
        return {"dictionaries": dictionaries, "rows": encoded_rows}

    def run_length_encode(self, values: list[Any]) -> list[tuple[Any, int]]:
        return [(value, sum(1 for _ in group)) for value, group in groupby(values)]

    def delta_encode(self, values: list[int]) -> list[int]:
        if not values:
            return []
        deltas = [values[0]]
        for previous, current in zip(values, values[1:]):
            deltas.append(current - previous)
        return deltas

    def pack(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload).encode("utf-8")
        return base64.b64encode(zlib.compress(raw)).decode("ascii")

    def unpack(self, payload: str) -> dict[str, Any]:
        raw = zlib.decompress(base64.b64decode(payload.encode("ascii")))
        return json.loads(raw.decode("utf-8"))


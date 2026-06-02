from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Any


def read_raw_biff_table(path: str | Path, encoding: str = "gbk") -> list[dict[str, Any]]:
    """Read the simple BIFF table stream exported by the legacy ERP.

    The old system writes a raw BIFF worksheet stream instead of an OLE `.xls`
    workbook. The records we need are LABEL and NUMBER cells.
    """
    data = Path(path).read_bytes()
    cells: dict[tuple[int, int], Any] = {}
    pos = 0
    while pos + 4 <= len(data):
        record_type, size = struct.unpack_from("<HH", data, pos)
        pos += 4
        payload = data[pos : pos + size]
        pos += size

        if record_type == 0x0204 and len(payload) >= 8:
            row, col, _xf, byte_length = struct.unpack_from("<HHHH", payload, 0)
            raw = payload[8 : 8 + byte_length]
            cells[(row, col)] = raw.decode(encoding, errors="replace").strip("\x00").strip()
        elif record_type == 0x0203 and len(payload) >= 14:
            row, col, _xf = struct.unpack_from("<HHH", payload, 0)
            value = struct.unpack_from("<d", payload, 6)[0]
            if math.isfinite(value) and value == int(value):
                value = int(value)
            cells[(row, col)] = value
        elif record_type == 0x000A:
            break

    if not cells:
        return []

    max_row = max(row for row, _col in cells)
    max_col = max(col for _row, col in cells)
    headers = [str(cells.get((0, col), "")).strip() for col in range(max_col + 1)]
    rows: list[dict[str, Any]] = []
    for row_index in range(1, max_row + 1):
        row = {headers[col]: cells.get((row_index, col), "") for col in range(max_col + 1) if headers[col]}
        if any(str(value).strip() for value in row.values()):
            rows.append(row)
    return rows

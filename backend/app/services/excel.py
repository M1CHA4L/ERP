from io import BytesIO
from typing import Iterable, Sequence

from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


def build_xlsx_response(filename: str, headers: Sequence[str], rows: Iterable[Sequence[object]]) -> StreamingResponse:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Report"

    worksheet.append(list(headers))
    header_fill = PatternFill("solid", fgColor="EAF2FF")
    for cell in worksheet[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill

    for row in rows:
        worksheet.append(list(row))

    for column_cells in worksheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column_cells)
        worksheet.column_dimensions[get_column_letter(column_cells[0].column)].width = min(max(max_length + 2, 12), 32)

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

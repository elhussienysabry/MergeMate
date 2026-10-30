"""Write the consolidated workbook, CSV, and report files."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from mergemate.consolidation import ConsolidationResult
from mergemate.exceptions import ExportError
from mergemate.reporting import write_report_csv, write_report_json

HEADER_FILL = PatternFill("solid", fgColor="0F766E")
SECTION_FILL = PatternFill("solid", fgColor="E2E8F0")
TITLE_FILL = PatternFill("solid", fgColor="0F172A")
WHITE_FONT = Font(color="FFFFFF", bold=True)
THIN_BORDER = Border(bottom=Side(style="thin", color="CBD5E1"))


def make_output_base_name(prefix: str = "mergemate") -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}"


def planned_output_paths(output_dir: str | Path, base_name: str) -> dict[str, Path]:
    output_dir = Path(output_dir)
    return {
        "excel": output_dir / f"{base_name}.xlsx",
        "csv": output_dir / f"{base_name}.csv",
        "report_json": output_dir / f"{base_name}_report.json",
        "report_csv": output_dir / f"{base_name}_report.csv",
    }


def _excel_value(value: Any, column: str) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    if isinstance(value, str) and len(value) > 32_767:
        raise ExportError(
            f"A value in column '{column}' is longer than Excel's 32,767-character "
            "cell limit. Shorten the value before exporting."
        )
    return value


def _style_header_row(ws: Worksheet, row: int, columns: int) -> None:
    for column in range(1, columns + 1):
        cell = ws.cell(row=row, column=column)
        cell.fill = HEADER_FILL
        cell.font = WHITE_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER
    ws.row_dimensions[row].height = 24


def _section(ws: Worksheet, row: int, title: str, columns: int = 2) -> None:
    for column in range(1, columns + 1):
        cell = ws.cell(row=row, column=column)
        cell.fill = SECTION_FILL
        cell.font = Font(bold=True, color="0F172A")
        cell.border = THIN_BORDER
    ws.cell(row=row, column=1, value=title)
    ws.row_dimensions[row].height = 20


def _autosize(ws: Worksheet, max_width: int = 45, sample_rows: int = 200) -> None:
    for column_cells in ws.iter_cols():
        letter = get_column_letter(column_cells[0].column)
        longest = 0
        for cell in column_cells[:sample_rows]:
            if cell.value is None:
                continue
            longest = max(longest, len(str(cell.value)))
        ws.column_dimensions[letter].width = min(max(10, longest + 2), max_width)


def _write_data_sheet(ws: Worksheet, result: ConsolidationResult) -> None:
    df = result.dataframe
    headers = [str(column) for column in df.columns]
    ws.append(headers)
    _style_header_row(ws, 1, len(headers))

    for row in df.itertuples(index=False, name=None):
        ws.append([_excel_value(value, headers[index]) for index, value in enumerate(row)])

    for index, column in enumerate(df.columns, start=1):
        series = df[column]
        number_format: str | None = None
        if pd.api.types.is_datetime64_any_dtype(series):
            number_format = "yyyy-mm-dd hh:mm:ss"
        elif not series.empty:
            first_value = next((value for value in series if not pd.isna(value)), None)
            if isinstance(first_value, dt.datetime):
                number_format = "yyyy-mm-dd hh:mm:ss"
            elif isinstance(first_value, dt.date):
                number_format = "yyyy-mm-dd"
            elif isinstance(first_value, dt.time):
                number_format = "hh:mm:ss"
        if number_format:
            for cell in ws[get_column_letter(index)][1:]:
                cell.number_format = number_format

    if ws.max_row > 1:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{ws.max_row}"
    ws.freeze_panes = "A2"
    _autosize(ws, max_width=42)


def _write_summary_sheet(ws: Worksheet, report: dict[str, Any]) -> None:
    ws.sheet_view.showGridLines = False
    ws.merge_cells("A1:B1")
    title = ws["A1"]
    title.value = "MergeMate Processing Summary"
    title.fill = TITLE_FILL
    title.font = Font(color="FFFFFF", bold=True, size=16)
    title.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 30
    ws.merge_cells("A2:B2")
    ws["A2"] = "Consolidated spreadsheet output and validation details"
    ws["A2"].font = Font(color="475569", italic=True)

    row = 4
    _section(ws, row, "Run")
    row += 1
    run_rows = [
        ("Generated at", report.get("generated_at", "")),
        ("Status", report.get("status", "")),
        ("Input files processed", report["inputs"]["processed_count"]),
        ("Input files failed", report["inputs"]["failed_count"]),
        (
            "Input rows",
            sum(file.get("rows", 0) for file in report["inputs"]["files"]),
        ),
        ("Output rows", report["output"]["rows"]),
        ("Output columns", report["output"]["columns"]),
        ("Processing duration (seconds)", report["timing"]["processing_seconds"]),
    ]
    for label, value in run_rows:
        ws.cell(row=row, column=1, value=label).font = Font(bold=True)
        ws.cell(row=row, column=2, value=value)
        row += 1

    row += 1
    _section(ws, row, "Options and applied changes")
    row += 1
    applied = report.get("applied", {})
    duplicates = report.get("duplicates", {})
    option_rows = [
        ("Missing-column strategy", applied.get("missing_column_strategy", "")),
        ("Duplicate handling", duplicates.get("mode", "")),
        ("Duplicate keep strategy", duplicates.get("keep", "")),
        ("Duplicate rows removed", duplicates.get("rows_removed", 0)),
        ("Source column", report.get("options", {}).get("source_column", "")),
        ("Trimmed columns", ", ".join(applied.get("trimmed_columns", [])) or "None"),
        ("Date columns parsed", ", ".join(applied.get("date_columns_parsed", [])) or "None"),
        (
            "Numeric columns converted",
            ", ".join(applied.get("numeric_columns_converted", [])) or "None",
        ),
    ]
    for label, value in option_rows:
        ws.cell(row=row, column=1, value=label).font = Font(bold=True)
        ws.cell(row=row, column=2, value=value)
        row += 1

    row += 1
    _section(ws, row, "Detected issues (not all are changes)")
    row += 1
    detected = report.get("detected", {})
    detected_rows = [
        ("Exact duplicate rows detected", detected.get("exact_duplicate_rows", 0)),
        (
            "Missing columns",
            _compact_mapping(detected.get("missing_columns", {})),
        ),
        (
            "File-specific columns",
            _compact_mapping(detected.get("file_specific_columns", {})),
        ),
        ("Conversion issues", len(detected.get("conversion_issues", []))),
    ]
    for label, value in detected_rows:
        ws.cell(row=row, column=1, value=label).font = Font(bold=True)
        ws.cell(row=row, column=2, value=value)
        ws.cell(row=row, column=2).alignment = Alignment(wrap_text=True, vertical="top")
        row += 1

    row += 1
    _section(ws, row, "Source files", columns=7)
    row += 1
    headers = ["File", "Type", "Worksheet", "Rows", "Columns", "Status", "Warnings"]
    for index, header in enumerate(headers, start=1):
        ws.cell(row=row, column=index, value=header)
    _style_header_row(ws, row, len(headers))
    row += 1
    for file in report["inputs"]["files"]:
        values = [
            file.get("name", ""),
            file.get("type", ""),
            file.get("worksheet", "—"),
            file.get("rows", 0),
            file.get("columns", 0),
            file.get("status", ""),
            " | ".join(file.get("warnings", [])),
        ]
        for index, value in enumerate(values, start=1):
            cell = ws.cell(row=row, column=index, value=value)
            cell.alignment = Alignment(vertical="top", wrap_text=index == 7)
        row += 1

    row += 1
    _section(ws, row, "Output files", columns=2)
    row += 1
    for label, value in report.get("output", {}).get("files", {}).items():
        ws.cell(row=row, column=1, value=label.replace("_", " ").title()).font = Font(
            bold=True
        )
        ws.cell(row=row, column=2, value=value)
        row += 1

    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 70
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 12
    ws.column_dimensions["F"].width = 12
    ws.column_dimensions["G"].width = 55
    ws.freeze_panes = "A4"


def _compact_mapping(value: dict[str, list[str]]) -> str:
    if not value:
        return "None"
    return "; ".join(f"{file}: {', '.join(columns)}" for file, columns in value.items())


def _write_mapping_sheet(ws: Worksheet, report: dict[str, Any]) -> None:
    headers = ["File", "Source Header", "Output Column", "Status", "Note"]
    ws.append(headers)
    _style_header_row(ws, 1, len(headers))
    for row in report.get("columns", {}).get("mapping", []):
        ws.append(
            [
                row.get("file", ""),
                row.get("source_header", ""),
                row.get("output_column", ""),
                row.get("status", ""),
                row.get("note", ""),
            ]
        )
    if ws.max_row > 1:
        ws.auto_filter.ref = f"A1:E{ws.max_row}"
    ws.freeze_panes = "A2"
    _autosize(ws, max_width=48)


def _write_issues_sheet(ws: Worksheet, report: dict[str, Any]) -> None:
    headers = ["Severity", "Code", "File", "Message"]
    ws.append(headers)
    _style_header_row(ws, 1, len(headers))
    issues = report.get("validation_issues", [])
    for issue in issues:
        ws.append(
            [
                issue.get("severity", ""),
                issue.get("code", ""),
                issue.get("file", ""),
                issue.get("message", ""),
            ]
        )
    if not issues:
        ws.append(["info", "none", "", "No validation issues were recorded."])
        ws["A2"].font = Font(italic=True, color="475569")
    if ws.max_row > 1:
        ws.auto_filter.ref = f"A1:D{ws.max_row}"
    ws.freeze_panes = "A2"
    _autosize(ws, max_width=100)


def export_workbook(
    result: ConsolidationResult,
    report: dict[str, Any],
    path: str | Path,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)

    data_sheet = workbook.create_sheet("Consolidated Data")
    _write_data_sheet(data_sheet, result)
    data_sheet.sheet_properties.tabColor = "0F766E"

    summary_sheet = workbook.create_sheet("Processing Summary")
    _write_summary_sheet(summary_sheet, report)
    summary_sheet.sheet_properties.tabColor = "334155"

    mapping_sheet = workbook.create_sheet("Column Mapping")
    _write_mapping_sheet(mapping_sheet, report)
    mapping_sheet.sheet_properties.tabColor = "64748B"

    issues_sheet = workbook.create_sheet("Validation Issues")
    _write_issues_sheet(issues_sheet, report)
    issues_sheet.sheet_properties.tabColor = "B45309"

    workbook.properties.title = "MergeMate consolidated output"
    workbook.properties.creator = "MergeMate"
    workbook.properties.description = (
        "Consolidated data plus processing summary, column mapping, and validation issues."
    )

    try:
        workbook.save(path)
    except OSError as exc:
        raise ExportError(f"Could not write workbook '{path.name}': {exc}") from exc
    return path


def export_csv(result: ConsolidationResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result.dataframe.to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
            date_format="%Y-%m-%d %H:%M:%S",
        )
    except OSError as exc:
        raise ExportError(f"Could not write CSV '{path.name}': {exc}") from exc
    return path


def export_all(
    result: ConsolidationResult,
    report: dict[str, Any],
    output_dir: str | Path,
    base_name: str,
    *,
    report_formats: str = "both",
) -> dict[str, Path]:
    """Write all requested outputs and return their paths."""
    if report_formats not in {"json", "csv", "both"}:
        raise ExportError(f"Unknown report format '{report_formats}'.")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = planned_output_paths(output_dir, base_name)

    requested_files = {
        "excel": paths["excel"].name,
        "csv": paths["csv"].name,
    }
    if report_formats in {"json", "both"}:
        requested_files["report_json"] = paths["report_json"].name
    if report_formats in {"csv", "both"}:
        requested_files["report_csv"] = paths["report_csv"].name
    report.setdefault("output", {})["files"] = requested_files

    export_workbook(result, report, paths["excel"])
    export_csv(result, paths["csv"])
    written: dict[str, Path] = {
        "excel": paths["excel"],
        "csv": paths["csv"],
    }
    if report_formats in {"json", "both"}:
        write_report_json(report, paths["report_json"])
        written["report_json"] = paths["report_json"]
    if report_formats in {"csv", "both"}:
        write_report_csv(report, paths["report_csv"])
        written["report_csv"] = paths["report_csv"]

    for key, path in written.items():
        if not path.exists() or path.stat().st_size == 0:
            raise ExportError(f"Expected output '{path.name}' was not created ({key}).")
    return written

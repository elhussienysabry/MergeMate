from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from mergemate.column_mapping import build_mapping_plan
from mergemate.consolidation import ConsolidationOptions, consolidate
from mergemate.exceptions import ExportError
from mergemate.export import export_all, planned_output_paths
from mergemate.file_readers import load_input_files
from mergemate.reporting import build_report, report_to_csv, report_to_json


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_export_workbook_sheets_and_formatting(
    pipeline_files: dict[str, Path], tmp_path: Path
) -> None:
    files, issues = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)
    result = consolidate(files, plan)
    report = build_report(result, files, issues=issues)

    written = export_all(result, report, tmp_path, "test_run", report_formats="both")

    workbook_path = written["excel"]
    assert workbook_path.exists()
    workbook = load_workbook(workbook_path)
    assert workbook.sheetnames == [
        "Consolidated Data",
        "Processing Summary",
        "Column Mapping",
        "Validation Issues",
    ]

    data_sheet = workbook["Consolidated Data"]
    assert data_sheet["A1"].value == "Source_File"
    assert data_sheet["B1"].value == "customer_name"
    assert data_sheet.max_row == 7
    assert data_sheet.freeze_panes == "A2"
    assert data_sheet.auto_filter.ref == "A1:F7"

    summary_sheet = workbook["Processing Summary"]
    assert summary_sheet["A1"].value == "MergeMate Processing Summary"

    mapping_sheet = workbook["Column Mapping"]
    assert mapping_sheet["A1"].value == "File"
    assert mapping_sheet["B1"].value == "Source Header"
    assert mapping_sheet.max_row >= 2

    issues_sheet = workbook["Validation Issues"]
    assert issues_sheet["A1"].value == "Severity"
    assert issues_sheet.max_row >= 2


def test_export_workbook_date_formatting(
    pipeline_files: dict[str, Path], tmp_path: Path
) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)
    result = consolidate(files, plan, ConsolidationOptions(date_columns=("date",)))
    report = build_report(result, files)

    written = export_all(result, report, tmp_path, "dated", report_formats="json")

    workbook = load_workbook(written["excel"])
    data_sheet = workbook["Consolidated Data"]
    date_column = [cell.value for cell in data_sheet[1]].index("date") + 1
    assert data_sheet.cell(row=2, column=date_column).number_format == "yyyy-mm-dd hh:mm:ss"


def test_report_accuracy(pipeline_files: dict[str, Path], tmp_path: Path) -> None:
    files, issues = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)
    result = consolidate(files, plan, ConsolidationOptions(duplicate_mode="exact"))
    report = build_report(result, files, issues=issues)
    export_all(result, report, tmp_path, "report_run", report_formats="both")

    assert report["tool"]["name"] == "MergeMate"
    assert report["status"] == "success"
    assert report["inputs"]["processed_count"] == 3
    assert report["inputs"]["failed_count"] == 0
    assert sum(item["rows"] for item in report["inputs"]["files"]) == 6
    assert report["output"]["rows"] == 4
    assert report["output"]["columns"] == 6
    assert report["output"]["source_counts"] == {"a.csv": 2, "b.csv": 1, "c.xlsx": 1}
    assert report["output"]["files"]["excel"] == "report_run.xlsx"
    assert report["output"]["files"]["report_json"] == "report_run_report.json"
    assert report["timing"]["processing_seconds"] >= 0
    assert report["duplicates"]["rows_removed"] == 2
    assert report["detected"]["exact_duplicate_rows"] == 2
    assert report["applied"]["duplicate_removal"]["rows_removed"] == 2
    assert report["columns"]["missing_columns"] == {"c.xlsx": ["date", "notes"]}
    assert any(row["source_header"] == "Customer Name" for row in report["columns"]["mapping"])


def test_report_marks_failed_files_as_partial(
    pipeline_files: dict[str, Path], tmp_path: Path
) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)
    result = consolidate(files, plan)
    report = build_report(
        result,
        files,
        failed_files=[{"name": "broken.csv", "code": "file_unreadable", "message": "Bad file"}],
    )

    assert report["status"] == "partial"
    assert report["inputs"]["failed_count"] == 1
    assert report["inputs"]["failed_files"][0]["name"] == "broken.csv"


def test_report_json_and_csv_do_not_copy_row_contents(
    pipeline_result, tmp_path: Path
) -> None:
    files, issues, _, result = pipeline_result
    report = build_report(result, files, issues=issues)

    json_text = report_to_json(report)
    csv_text = report_to_csv(report)
    parsed = json.loads(json_text)

    assert parsed["output"]["rows"] == 6
    assert "Alice" not in json_text
    assert "Alice" not in csv_text
    assert "output.rows" in csv_text
    assert "validation_issues" in csv_text
    assert (tmp_path / "unused").parent.exists()


def test_export_all_rejects_unknown_report_format(
    pipeline_result, tmp_path: Path
) -> None:
    files, _, _, result = pipeline_result
    report = build_report(result, files)

    with pytest.raises(ExportError, match="Unknown report format"):
        export_all(result, report, tmp_path, "bad", report_formats="xml")


def test_planned_output_paths(tmp_path: Path) -> None:
    paths = planned_output_paths(tmp_path, "demo")

    assert paths["excel"].name == "demo.xlsx"
    assert paths["csv"].name == "demo.csv"
    assert paths["report_json"].name == "demo_report.json"
    assert paths["report_csv"].name == "demo_report.csv"


def test_original_inputs_are_never_modified(
    pipeline_files: dict[str, Path], tmp_path: Path
) -> None:
    before = {name: _sha256(path) for name, path in pipeline_files.items()}

    files, issues = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)
    result = consolidate(files, plan, ConsolidationOptions(duplicate_mode="exact"))
    report = build_report(result, files, issues=issues)
    export_all(result, report, tmp_path, "immutable", report_formats="both")

    after = {name: _sha256(path) for name, path in pipeline_files.items()}
    assert before == after


def test_report_output_file_names_are_updated_by_export(
    pipeline_result, tmp_path: Path
) -> None:
    files, issues, _, result = pipeline_result
    report = build_report(result, files, issues=issues)
    assert report["output"]["files"] == {}

    export_all(result, report, tmp_path, "names", report_formats="both")

    assert report["output"]["files"] == {
        "excel": "names.xlsx",
        "csv": "names.csv",
        "report_json": "names_report.json",
        "report_csv": "names_report.csv",
    }
    assert (tmp_path / "names_report.json").exists()
    assert (tmp_path / "names_report.csv").exists()


def test_exported_csv_can_be_read_back(pipeline_result, tmp_path: Path) -> None:
    files, issues, _, result = pipeline_result
    report = build_report(result, files, issues=issues)
    written = export_all(result, report, tmp_path, "roundtrip", report_formats="json")

    loaded = pd.read_csv(written["csv"], encoding="utf-8-sig")

    assert len(loaded) == result.output_row_count
    assert "Source_File" in loaded.columns
    assert loaded["customer_name"].tolist() == result.dataframe["customer_name"].tolist()

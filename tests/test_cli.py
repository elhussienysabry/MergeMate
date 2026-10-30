from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, cwd: Path = PROJECT_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mergemate.cli", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def write_simple_csv(path: Path, rows: list[tuple[str, int]]) -> None:
    path.write_text(
        "name,amount\n" + "".join(f"{name},{amount}\n" for name, amount in rows),
        encoding="utf-8",
    )


def test_cli_help() -> None:
    completed = run_cli("--help")

    assert completed.returncode == 0
    assert "merge" in completed.stdout
    assert "Consolidate" in completed.stdout


def test_cli_merge_end_to_end(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    write_simple_csv(inputs / "a.csv", [("Alice", 10), ("Bob", 20)])
    write_simple_csv(inputs / "b.csv", [("Carol", 30), ("Bob", 20)])
    output = tmp_path / "output"

    completed = run_cli(
        "merge",
        str(inputs),
        "--output",
        str(output),
        "--duplicates",
        "exact",
        "--report-format",
        "both",
    )

    assert completed.returncode == 0, completed.stderr
    assert "Consolidated 3 rows" in completed.stdout
    files = sorted(output.glob("*"))
    assert len(files) == 4
    workbook = load_workbook(next(output.glob("*.xlsx")))
    assert workbook.sheetnames == [
        "Consolidated Data",
        "Processing Summary",
        "Column Mapping",
        "Validation Issues",
    ]
    report = json.loads(next(output.glob("*_report.json")).read_text(encoding="utf-8"))
    assert report["status"] == "success"
    assert report["inputs"]["processed_count"] == 2
    assert report["output"]["rows"] == 3
    assert report["duplicates"]["rows_removed"] == 1


def test_cli_unsupported_file_returns_one(tmp_path: Path) -> None:
    bad = tmp_path / "notes.txt"
    bad.write_text("not a spreadsheet", encoding="utf-8")

    completed = run_cli("merge", str(bad), "--output", str(tmp_path / "out"))

    assert completed.returncode == 1
    assert "Unsupported" in completed.stderr


def test_cli_no_supported_files_returns_one(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    completed = run_cli("merge", str(empty), "--output", str(tmp_path / "out"))

    assert completed.returncode == 1
    assert "no supported" in completed.stderr.lower()


def test_cli_strict_failure_and_skip_invalid(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    write_simple_csv(inputs / "good.csv", [("Alice", 10)])
    (inputs / "bad.csv").write_text("", encoding="utf-8")
    output = tmp_path / "output"

    strict = run_cli("merge", str(inputs), "--output", str(output))
    assert strict.returncode == 1
    assert "failed validation" in strict.stderr

    partial = run_cli(
        "merge",
        str(inputs),
        "--output",
        str(output),
        "--skip-invalid",
        "--report-format",
        "both",
    )
    assert partial.returncode == 3, partial.stderr
    report = json.loads(next(output.glob("*_report.json")).read_text(encoding="utf-8"))
    assert report["status"] == "partial"
    assert report["inputs"]["failed_count"] == 1
    assert report["output"]["rows"] == 1


def test_cli_worksheet_selection(tmp_path: Path) -> None:
    workbook_path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        pd.DataFrame({"name": ["Jan"], "amount": [1]}).to_excel(
            writer, index=False, sheet_name="Jan"
        )
        pd.DataFrame({"name": ["Feb"], "amount": [2]}).to_excel(
            writer, index=False, sheet_name="Feb"
        )
    output = tmp_path / "output"

    completed = run_cli(
        "merge",
        str(workbook_path),
        "--output",
        str(output),
        "--sheet",
        "book.xlsx=Feb",
        "--report-format",
        "both",
    )

    assert completed.returncode == 0, completed.stderr
    csv_path = next(
        path for path in output.glob("*.csv") if not path.name.endswith("_report.csv")
    )
    data = pd.read_csv(csv_path)
    assert data["name"].tolist() == ["Feb"]


def test_cli_mapping_json(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    first.write_text("Customer Name,Amount\nAlice,10\n", encoding="utf-8")
    second = tmp_path / "second.csv"
    second.write_text("CustomerName,Amount\nBob,20\n", encoding="utf-8")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(
        json.dumps({"files": {"second.csv": {"CustomerName": "customer_name"}}}),
        encoding="utf-8",
    )
    output = tmp_path / "output"

    completed = run_cli(
        "merge",
        str(first),
        str(second),
        "--output",
        str(output),
        "--mapping",
        str(mapping),
        "--report-format",
        "both",
    )

    assert completed.returncode == 0, completed.stderr
    csv_path = next(
        path for path in output.glob("*.csv") if not path.name.endswith("_report.csv")
    )
    data = pd.read_csv(csv_path)
    assert "customer_name" in data.columns
    assert data["customer_name"].tolist() == ["Alice", "Bob"]


def test_cli_missing_columns_reject(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    first.write_text("name,amount,date\nAlice,10,2024-01-01\n", encoding="utf-8")
    second = tmp_path / "second.csv"
    second.write_text("name,amount\nBob,20\n", encoding="utf-8")

    completed = run_cli(
        "merge",
        str(first),
        str(second),
        "--output",
        str(tmp_path / "output"),
        "--missing-columns",
        "reject",
    )

    assert completed.returncode == 1
    assert "missing columns" in completed.stderr.lower()


def test_cli_output_directory_is_ignored_while_scanning(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    write_simple_csv(inputs / "a.csv", [("Alice", 10)])
    output = inputs / "out"
    output.mkdir()
    write_simple_csv(output / "old_generated.csv", [("ShouldNotAppear", 999)])

    completed = run_cli(
        "merge",
        str(inputs),
        "--output",
        str(output),
        "--report-format",
        "both",
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(next(output.glob("*_report.json")).read_text(encoding="utf-8"))
    assert report["inputs"]["processed_count"] == 1
    assert report["output"]["rows"] == 1


def test_cli_recursive_directory(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    nested = inputs / "nested"
    nested.mkdir(parents=True)
    write_simple_csv(inputs / "a.csv", [("Alice", 10)])
    write_simple_csv(nested / "b.csv", [("Bob", 20)])
    output = tmp_path / "output"

    completed = run_cli(
        "merge",
        str(inputs),
        "--output",
        str(output),
        "--recursive",
        "--report-format",
        "both",
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(next(output.glob("*_report.json")).read_text(encoding="utf-8"))
    assert report["inputs"]["processed_count"] == 2
    assert report["output"]["rows"] == 2


def test_cli_invalid_sheet_syntax(tmp_path: Path) -> None:
    path = tmp_path / "a.csv"
    write_simple_csv(path, [("Alice", 10)])

    completed = run_cli("merge", str(path), "--sheet", "missing-equals-sign")

    assert completed.returncode == 1
    assert "Invalid --sheet" in completed.stderr

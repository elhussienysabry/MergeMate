from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from mergemate.exceptions import (
    EmptyFileError,
    FileTooLargeError,
    MalformedFileError,
    TooManyColumnsError,
    TooManyRowsError,
    UnsupportedFileTypeError,
    WorksheetError,
)
from mergemate.file_readers import (
    ReadOptions,
    check_total_rows,
    list_excel_sheets,
    load_input_files,
    read_csv_file,
    read_excel_file,
    read_input_file,
)


def test_read_csv_auto_detects_semicolon_and_comma_decimal(tmp_path: Path) -> None:
    path = tmp_path / "european.csv"
    path.write_text("name;amount\nalpha;1,5\nbeta;2,25\n", encoding="utf-8")

    loaded = read_csv_file(path)

    assert loaded.csv_delimiter == ";"
    assert loaded.csv_decimal == ","
    assert loaded.csv_encoding == "utf-8"
    assert loaded.dataframe["amount"].tolist() == [1.5, 2.25]
    assert loaded.row_count == 2


def test_read_csv_explicit_encoding(tmp_path: Path) -> None:
    path = tmp_path / "latin.csv"
    path.write_bytes("name\ncafé\n".encode("latin-1"))

    loaded = read_csv_file(path, ReadOptions(csv_encoding="latin-1"))

    assert loaded.dataframe.loc[0, "name"] == "café"


def test_read_excel_worksheet_selection(tmp_path: Path) -> None:
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"name": ["January"], "value": [1]}).to_excel(
            writer, index=False, sheet_name="Jan"
        )
        pd.DataFrame({"name": ["February"], "value": [2]}).to_excel(
            writer, index=False, sheet_name="Feb"
        )

    assert list_excel_sheets(path) == ["Jan", "Feb"]
    loaded = read_excel_file(path, ReadOptions(worksheet="Feb"))

    assert loaded.sheet_name == "Feb"
    assert loaded.dataframe.loc[0, "name"] == "February"
    assert loaded.dataframe.loc[0, "value"] == 2


def test_read_excel_defaults_to_first_sheet_with_warning(tmp_path: Path) -> None:
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"value": [1]}).to_excel(writer, index=False, sheet_name="First")
        pd.DataFrame({"value": [2]}).to_excel(writer, index=False, sheet_name="Second")

    loaded = read_excel_file(path)

    assert loaded.sheet_name == "First"
    assert any("worksheets" in warning for warning in loaded.warnings)


def test_read_input_file_dispatches_csv_and_excel(
    pipeline_files: dict[str, Path],
) -> None:
    csv_loaded = read_input_file(pipeline_files["a"])
    excel_loaded = read_input_file(pipeline_files["c"])

    assert csv_loaded.file_type == "CSV"
    assert excel_loaded.file_type == "Excel"
    assert excel_loaded.sheet_name == "Records"


def test_unsupported_file_type(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")

    with pytest.raises(UnsupportedFileTypeError, match="Unsupported"):
        read_input_file(path)


def test_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(EmptyFileError, match="empty"):
        read_csv_file(path)


def test_header_only_csv_is_empty(tmp_path: Path) -> None:
    path = tmp_path / "header.csv"
    path.write_text("a,b\n", encoding="utf-8")

    with pytest.raises(EmptyFileError):
        read_csv_file(path)


def test_malformed_csv(tmp_path: Path) -> None:
    path = tmp_path / "broken.csv"
    path.write_text('a,b\n"unclosed,1\n2,3\n', encoding="utf-8")

    with pytest.raises(MalformedFileError, match="Could not parse"):
        read_csv_file(path)


def test_missing_worksheet(tmp_path: Path) -> None:
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"value": [1]}).to_excel(writer, index=False, sheet_name="Only")

    with pytest.raises(WorksheetError, match="not found"):
        read_excel_file(path, ReadOptions(worksheet="Missing"))


def test_file_size_limit(tmp_path: Path) -> None:
    path = tmp_path / "small.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")

    with pytest.raises(FileTooLargeError, match="limit"):
        read_csv_file(path, ReadOptions(max_file_size=5))


def test_row_limit(tmp_path: Path) -> None:
    path = tmp_path / "rows.csv"
    path.write_text("a\n1\n2\n", encoding="utf-8")

    with pytest.raises(TooManyRowsError, match="limit"):
        read_csv_file(path, ReadOptions(max_rows=1))


def test_column_limit(tmp_path: Path) -> None:
    path = tmp_path / "cols.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")

    with pytest.raises(TooManyColumnsError, match="limit"):
        read_csv_file(path, ReadOptions(max_columns=1))


def test_blank_header_is_named_with_warning(tmp_path: Path) -> None:
    path = tmp_path / "blank.csv"
    path.write_text("name,\nAlice,1\n", encoding="utf-8")

    loaded = read_csv_file(path)

    assert "column_2" in loaded.columns
    assert any("no header" in warning for warning in loaded.warnings)


def test_load_input_files_collects_errors_and_continues(tmp_path: Path) -> None:
    good = tmp_path / "good.csv"
    good.write_text("a,b\n1,2\n", encoding="utf-8")
    bad = tmp_path / "bad.csv"
    bad.write_text("", encoding="utf-8")

    files, issues = load_input_files([good, bad])

    assert [file.display_name for file in files] == ["good.csv"]
    assert any(issue.severity == "error" and issue.file == "bad.csv" for issue in issues)


def test_load_input_files_rejects_too_many_files(tmp_path: Path) -> None:
    paths = []
    for index in range(3):
        path = tmp_path / f"{index}.csv"
        path.write_text("a\n1\n", encoding="utf-8")
        paths.append(path)

    files, issues = load_input_files(paths, max_files=2)

    assert files == []
    assert issues[0].code == "too_many_files"


def test_check_total_rows() -> None:
    from mergemate.file_readers import LoadedFile

    loaded = LoadedFile(
        path=Path("a.csv"),
        display_name="a.csv",
        file_type="CSV",
        dataframe=pd.DataFrame({"a": [1, 2, 3]}),
    )

    issue = check_total_rows([loaded], max_total_rows=2)

    assert issue is not None
    assert issue.code == "too_many_total_rows"
    assert check_total_rows([loaded], max_total_rows=3) is None


def test_csv_delimiter_and_decimal_conflict(tmp_path: Path) -> None:
    path = tmp_path / "conflict.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")

    with pytest.raises(MalformedFileError, match="both delimiter and decimal"):
        read_csv_file(path, ReadOptions(csv_delimiter=",", csv_decimal=","))

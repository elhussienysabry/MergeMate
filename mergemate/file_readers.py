"""Read CSV and Excel inputs without modifying the originals."""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd

from mergemate.config import (
    MAX_COLUMNS,
    MAX_FILE_SIZE_BYTES,
    MAX_FILES,
    MAX_ROWS_PER_FILE,
    SUPPORTED_EXTENSIONS,
)
from mergemate.exceptions import (
    EmptyFileError,
    FileTooLargeError,
    MalformedFileError,
    TooManyColumnsError,
    TooManyRowsError,
    UnsupportedFileTypeError,
    WorksheetError,
)
from mergemate.validation import ValidationIssue


@dataclass(frozen=True)
class ReadOptions:
    """Options that affect how an input file is parsed."""

    csv_delimiter: str | None = None
    csv_encoding: str | None = None
    csv_decimal: str | None = None
    worksheet: str | int | None = None
    max_file_size: int = MAX_FILE_SIZE_BYTES
    max_rows: int = MAX_ROWS_PER_FILE
    max_columns: int = MAX_COLUMNS


@dataclass
class LoadedFile:
    """A successfully parsed input file and its safe metadata."""

    path: Path
    display_name: str
    file_type: str
    dataframe: pd.DataFrame
    sheet_name: str | None = None
    size_bytes: int = 0
    warnings: tuple[str, ...] = ()
    csv_delimiter: str | None = None
    csv_encoding: str | None = None
    csv_decimal: str | None = None

    @property
    def row_count(self) -> int:
        return len(self.dataframe)

    @property
    def column_count(self) -> int:
        return len(self.dataframe.columns)

    @property
    def columns(self) -> list[str]:
        return [str(column) for column in self.dataframe.columns]

    def summary(self) -> dict[str, object]:
        data: dict[str, object] = {
            "name": self.display_name,
            "type": self.file_type,
            "rows": self.row_count,
            "columns": self.column_count,
            "size_bytes": self.size_bytes,
            "status": "processed",
        }
        if self.sheet_name is not None:
            data["worksheet"] = self.sheet_name
        if self.csv_delimiter is not None:
            data["csv_delimiter"] = _visible_delimiter(self.csv_delimiter)
        if self.csv_encoding is not None:
            data["csv_encoding"] = self.csv_encoding
        if self.warnings:
            data["warnings"] = list(self.warnings)
        return data


def _visible_delimiter(delimiter: str) -> str:
    return {"\t": "tab", ",": "comma", ";": "semicolon", "|": "pipe"}.get(
        delimiter, delimiter
    )


def _validate_path(path: Path, max_file_size: int) -> Path:
    path = Path(path).expanduser()
    if not path.exists():
        raise UnsupportedFileTypeError(f"File not found: {path.name}")
    if not path.is_file():
        raise UnsupportedFileTypeError(f"Not a regular file: {path.name}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix or '(none)'}'. Use {supported} files."
        )
    size = path.stat().st_size
    if size == 0:
        raise EmptyFileError(f"'{path.name}' is empty.")
    if size > max_file_size:
        raise FileTooLargeError(
            f"'{path.name}' is {size / 1024 / 1024:.1f} MB; the limit is "
            f"{max_file_size / 1024 / 1024:.0f} MB per file."
        )
    return path


def detect_encoding(path: Path) -> str:
    """Return the first workable text encoding for a CSV file."""
    raw = Path(path).read_bytes()[:131_072]
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        return encoding
    return "latin-1"


def detect_delimiter(text: str) -> str:
    """Detect common CSV delimiters without executing file content."""
    sample = "\n".join(text.splitlines()[:20])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        if dialect.delimiter in {",", ";", "\t", "|"}:
            return dialect.delimiter
    except csv.Error:
        pass

    first_line = next((line for line in text.splitlines() if line.strip()), "")
    counts = {delimiter: first_line.count(delimiter) for delimiter in (",", ";", "\t", "|")}
    best = max(counts, key=counts.get)
    return best if counts[best] else ","


def detect_decimal(text: str, delimiter: str) -> str:
    """Detect comma decimals when the delimiter makes that unambiguous."""
    if delimiter == ",":
        return "."
    sample = "\n".join(text.splitlines()[:30])
    if re.search(r"(?<!\d)\d+,\d+", sample):
        return ","
    return "."


def _clean_column_names(
    df: pd.DataFrame, file_name: str
) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    names: list[str] = []
    for index, raw_name in enumerate(df.columns):
        name = str(raw_name).replace("\ufeff", "").strip()
        if not name or re.fullmatch(r"Unnamed: \d+", name, flags=re.IGNORECASE):
            name = f"column_{index + 1}"
            warnings.append(
                f"Column {index + 1} had no header and was named '{name}'."
            )
        names.append(name)

    if len(set(names)) != len(names):
        duplicates = sorted({name for name in names if names.count(name) > 1})
        raise MalformedFileError(
            f"'{file_name}' has duplicate column headers: {', '.join(duplicates)}. "
            "Rename the headers so each column is unique."
        )

    cleaned = df.copy()
    cleaned.columns = names
    return cleaned, warnings


def _prepare_dataframe(
    df: pd.DataFrame,
    *,
    file_name: str,
    options: ReadOptions,
) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []

    empty_rows = int(df.isna().all(axis=1).sum())
    if empty_rows:
        df = df.dropna(how="all")
        warnings.append(f"Dropped {empty_rows:,} completely empty row(s).")

    empty_columns = int(df.isna().all(axis=0).sum())
    if empty_columns:
        df = df.dropna(axis=1, how="all")
        warnings.append(f"Dropped {empty_columns:,} completely empty column(s).")

    if df.empty:
        raise EmptyFileError(
            f"'{file_name}' contains no usable rows after empty rows were removed."
        )

    df, column_warnings = _clean_column_names(df, file_name)
    warnings.extend(column_warnings)

    if len(df.columns) > options.max_columns:
        raise TooManyColumnsError(
            f"'{file_name}' has {len(df.columns):,} columns; the limit is "
            f"{options.max_columns:,}."
        )
    if len(df) > options.max_rows:
        raise TooManyRowsError(
            f"'{file_name}' has {len(df):,} rows; the limit is "
            f"{options.max_rows:,} rows per file."
        )

    return df.reset_index(drop=True), warnings


def read_csv_file(path: str | Path, options: ReadOptions | None = None) -> LoadedFile:
    """Read one CSV file using auto-detection unless explicit options are set."""
    options = options or ReadOptions()
    path = _validate_path(Path(path), options.max_file_size)
    encoding = options.csv_encoding or detect_encoding(path)
    try:
        text = path.read_text(encoding=encoding)
    except (OSError, UnicodeError) as exc:
        raise MalformedFileError(f"Could not read '{path.name}' as text: {exc}") from exc

    delimiter = options.csv_delimiter or detect_delimiter(text)
    decimal = options.csv_decimal or detect_decimal(text, delimiter)
    if delimiter == "," and decimal == ",":
        raise MalformedFileError(
            f"'{path.name}' cannot use a comma as both delimiter and decimal separator. "
            "Choose a different delimiter or use dot decimals."
        )

    try:
        df = pd.read_csv(
            path,
            sep=delimiter,
            decimal=decimal,
            encoding=encoding,
            low_memory=False,
        )
    except pd.errors.EmptyDataError as exc:
        raise EmptyFileError(f"'{path.name}' contains no CSV data.") from exc
    except (pd.errors.ParserError, UnicodeError, ValueError, OSError) as exc:
        raise MalformedFileError(
            f"Could not parse '{path.name}' as CSV. Check the delimiter, encoding, "
            f"and row structure. Details: {exc}"
        ) from exc

    df, warnings = _prepare_dataframe(df, file_name=path.name, options=options)
    return LoadedFile(
        path=path,
        display_name=path.name,
        file_type="CSV",
        dataframe=df,
        size_bytes=path.stat().st_size,
        warnings=tuple(warnings),
        csv_delimiter=delimiter,
        csv_encoding=encoding,
        csv_decimal=decimal,
    )


def list_excel_sheets(path: str | Path, options: ReadOptions | None = None) -> list[str]:
    """Return worksheet names for an Excel workbook."""
    options = options or ReadOptions()
    path = _validate_path(Path(path), options.max_file_size)
    try:
        with pd.ExcelFile(path, engine="openpyxl") as workbook:
            sheets = [str(name) for name in workbook.sheet_names]
    except Exception as exc:
        raise WorksheetError(
            f"Could not open worksheets in '{path.name}'. The file may be corrupt "
            f"or password-protected. Details: {exc}"
        ) from exc
    if not sheets:
        raise WorksheetError(f"'{path.name}' does not contain any worksheets.")
    return sheets


def read_excel_file(path: str | Path, options: ReadOptions | None = None) -> LoadedFile:
    """Read one worksheet from an .xlsx workbook."""
    options = options or ReadOptions()
    path = _validate_path(Path(path), options.max_file_size)
    warnings: list[str] = []

    try:
        with pd.ExcelFile(path, engine="openpyxl") as workbook:
            sheets = [str(name) for name in workbook.sheet_names]
            if not sheets:
                raise WorksheetError(f"'{path.name}' does not contain any worksheets.")
            if options.worksheet is None:
                sheet_name: str | int = 0
                selected_name = sheets[0]
                if len(sheets) > 1:
                    warnings.append(
                        f"Workbook has {len(sheets)} worksheets; using the first "
                        f"worksheet ('{selected_name}'). Select another worksheet if needed."
                    )
            elif isinstance(options.worksheet, int):
                if options.worksheet < 0 or options.worksheet >= len(sheets):
                    raise WorksheetError(
                        f"Worksheet index {options.worksheet} is out of range for "
                        f"'{path.name}'. Available worksheets: {', '.join(sheets)}."
                    )
                sheet_name = options.worksheet
                selected_name = sheets[options.worksheet]
            else:
                if options.worksheet not in sheets:
                    raise WorksheetError(
                        f"Worksheet '{options.worksheet}' was not found in '{path.name}'. "
                        f"Available worksheets: {', '.join(sheets)}."
                    )
                sheet_name = options.worksheet
                selected_name = options.worksheet

            df = pd.read_excel(workbook, sheet_name=sheet_name, engine="openpyxl")
    except WorksheetError:
        raise
    except Exception as exc:
        raise WorksheetError(
            f"Could not read worksheet '{options.worksheet or 'first'}' from "
            f"'{path.name}'. The workbook may be corrupt or password-protected. "
            f"Details: {exc}"
        ) from exc

    df, data_warnings = _prepare_dataframe(df, file_name=path.name, options=options)
    warnings.extend(data_warnings)
    return LoadedFile(
        path=path,
        display_name=path.name,
        file_type="Excel",
        dataframe=df,
        sheet_name=selected_name,
        size_bytes=path.stat().st_size,
        warnings=tuple(warnings),
    )


def read_input_file(path: str | Path, options: ReadOptions | None = None) -> LoadedFile:
    """Dispatch to the CSV or Excel reader based on the file extension."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return read_csv_file(path, options)
    if suffix == ".xlsx":
        return read_excel_file(path, options)
    _validate_path(path, (options or ReadOptions()).max_file_size)
    raise UnsupportedFileTypeError(
        f"Unsupported file type '{suffix or '(none)'}'. Use .csv or .xlsx files."
    )


def _make_unique_names(files: list[LoadedFile]) -> None:
    counts: dict[str, int] = {}
    for loaded in files:
        base = loaded.display_name
        counts[base] = counts.get(base, 0) + 1
        if counts[base] > 1:
            loaded.display_name = f"{base} ({counts[base]})"


def _sheet_override_for(path: Path, overrides: dict[str, str]) -> str | None:
    return overrides.get(str(path)) or overrides.get(path.name)


def load_input_files(
    paths: Iterable[str | Path],
    options: ReadOptions | None = None,
    *,
    sheet_overrides: dict[str, str] | None = None,
    max_files: int = MAX_FILES,
) -> tuple[list[LoadedFile], list[ValidationIssue]]:
    """Read several files, collecting per-file errors instead of aborting."""
    options = options or ReadOptions()
    sheet_overrides = sheet_overrides or {}
    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        key = path.resolve()
        if key not in seen:
            seen.add(key)
            unique_paths.append(path)

    issues: list[ValidationIssue] = []
    if len(unique_paths) > max_files:
        issues.append(
            ValidationIssue(
                severity="error",
                code="too_many_files",
                message=(
                    f"Selected {len(unique_paths)} files; the limit is {max_files} "
                    "files per run."
                ),
            )
        )
        return [], issues

    loaded: list[LoadedFile] = []
    for path in unique_paths:
        worksheet = _sheet_override_for(path, sheet_overrides)
        file_options = replace(options, worksheet=worksheet)
        try:
            loaded_file = read_input_file(path, file_options)
        except Exception as exc:  # expected domain errors and unreadable files
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="file_unreadable",
                    message=str(exc),
                    file=path.name,
                )
            )
            continue

        loaded.append(loaded_file)
        for warning in loaded_file.warnings:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="file_warning",
                    message=warning,
                    file=loaded_file.display_name,
                )
            )

    _make_unique_names(loaded)
    return loaded, issues


def check_total_rows(
    files: list[LoadedFile], max_total_rows: int
) -> ValidationIssue | None:
    total = sum(file.row_count for file in files)
    if total > max_total_rows:
        return ValidationIssue(
            severity="error",
            code="too_many_total_rows",
            message=(
                f"Selected files contain {total:,} rows in total; the limit is "
                f"{max_total_rows:,} rows per run. Split the work into smaller runs."
            ),
        )
    return None

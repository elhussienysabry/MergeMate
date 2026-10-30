"""Command-line interface for repeatable MergeMate runs."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from mergemate.column_mapping import build_mapping_plan
from mergemate.config import (
    APP_VERSION,
    CSV_DECIMAL_OPTIONS,
    CSV_DELIMITER_OPTIONS,
    CSV_ENCODING_OPTIONS,
    DEFAULT_SOURCE_COLUMN,
    MAX_FILES,
    MAX_ROWS_PER_FILE,
    MAX_TOTAL_ROWS,
    SUPPORTED_EXTENSIONS,
)
from mergemate.consolidation import ConsolidationOptions, consolidate
from mergemate.exceptions import MergeMateError
from mergemate.export import export_all, make_output_base_name
from mergemate.file_readers import (
    ReadOptions,
    check_total_rows,
    load_input_files,
)
from mergemate.reporting import build_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mergemate",
        description=(
            "MergeMate consolidates multiple CSV and Excel files into one workbook "
            "with a processing report."
        ),
        epilog=(
            "Examples:\n"
            "  python -m mergemate.cli merge data/sample_inputs --output output\n"
            "  python -m mergemate.cli merge data/sample_inputs --output output "
            "--missing-columns blank --duplicates exact\n"
            "  python -m mergemate.cli merge input/ --output output "
            "--mapping examples/mapping.json --report-format both\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {APP_VERSION}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    merge = subparsers.add_parser(
        "merge",
        help="Consolidate CSV/XLSX files.",
        description=(
            "Read the selected files, review column mappings, consolidate, and export "
            "an Excel workbook, a CSV, and a processing report."
        ),
    )
    merge.add_argument(
        "inputs",
        nargs="+",
        help="CSV/XLSX files or directories containing inputs.",
    )
    merge.add_argument(
        "-o",
        "--output",
        default="output",
        help="Output directory (default: output).",
    )
    merge.add_argument(
        "--sheet",
        action="append",
        default=[],
        metavar="FILE=SHEET",
        help=(
            "Worksheet to read from an .xlsx file. Repeat for multiple files. "
            "If omitted, the first worksheet is used."
        ),
    )
    merge.add_argument(
        "--mapping",
        type=Path,
        help=(
            "Optional JSON mapping file. Format: "
            '{"files": {"file.csv": {"Source Header": "output_column"}}}. '
            "Use null to ignore a source column."
        ),
    )
    merge.add_argument(
        "--missing-columns",
        choices=["blank", "exclude", "reject"],
        default="blank",
        help=(
            "How to handle columns missing from some files: fill blanks (default), "
            "exclude the column, or reject incompatible files."
        ),
    )
    merge.add_argument(
        "--duplicates",
        choices=["keep-all", "exact", "keys"],
        default="keep-all",
        help="Duplicate policy (default: keep-all).",
    )
    merge.add_argument(
        "--key-columns",
        default="",
        help="Comma-separated output columns used when --duplicates keys is selected.",
    )
    merge.add_argument(
        "--keep",
        choices=["first", "last"],
        default="first",
        help="Which duplicate to keep for key-based removal (default: first).",
    )
    merge.add_argument(
        "--source-column",
        default=DEFAULT_SOURCE_COLUMN,
        help=f"Name of the source-file column (default: {DEFAULT_SOURCE_COLUMN}).",
    )
    merge.add_argument(
        "--trim",
        default="",
        help="Comma-separated text columns to trim.",
    )
    merge.add_argument(
        "--parse-date",
        default="",
        help="Comma-separated columns to parse as dates.",
    )
    merge.add_argument(
        "--numeric",
        default="",
        help="Comma-separated columns to convert to numbers.",
    )
    merge.add_argument(
        "--delimiter",
        choices=list(CSV_DELIMITER_OPTIONS),
        default="auto",
        help="CSV delimiter (default: auto-detect).",
    )
    merge.add_argument(
        "--encoding",
        choices=list(CSV_ENCODING_OPTIONS),
        default="auto",
        help="CSV text encoding (default: auto-detect).",
    )
    merge.add_argument(
        "--decimal",
        choices=list(CSV_DECIMAL_OPTIONS),
        default="auto",
        help="CSV decimal separator (default: auto-detect).",
    )
    merge.add_argument(
        "--report-format",
        choices=["json", "csv", "both"],
        default="json",
        help="Processing report format (default: json).",
    )
    merge.add_argument(
        "--skip-invalid",
        action="store_true",
        help=(
            "Continue with readable files when some inputs fail validation. "
            "Exits with code 3 when a partial result is written."
        ),
    )
    merge.add_argument(
        "--recursive",
        action="store_true",
        help="Search directories recursively.",
    )
    merge.add_argument(
        "--max-rows",
        type=int,
        default=MAX_ROWS_PER_FILE,
        help=f"Maximum rows per input file (default: {MAX_ROWS_PER_FILE:,}).",
    )
    merge.add_argument(
        "--max-files",
        type=int,
        default=MAX_FILES,
        help=f"Maximum number of input files (default: {MAX_FILES}).",
    )
    merge.add_argument(
        "--quiet",
        action="store_true",
        help="Only print the final output locations and errors.",
    )
    return parser


def _split_csv_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_sheet_overrides(values: Sequence[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(
                f"Invalid --sheet value '{value}'. Use FILE=SHEET, for example "
                "monthly.xlsx=January."
            )
        file_name, sheet_name = value.split("=", 1)
        if not file_name.strip() or not sheet_name.strip():
            raise ValueError(
                f"Invalid --sheet value '{value}'. Both the file and worksheet are required."
            )
        overrides[file_name.strip()] = sheet_name.strip()
        overrides.setdefault(Path(file_name.strip()).name, sheet_name.strip())
    return overrides


def _load_mapping(path: Path | None) -> tuple[dict[str, dict[str, str | None]], dict[str, list[str]]]:
    if path is None:
        return {}, {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read mapping file '{path}': {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("The mapping file must contain a JSON object.")

    mapping_section = raw.get("files", raw)
    if not isinstance(mapping_section, dict):
        raise ValueError("The mapping file's 'files' value must be an object.")
    overrides: dict[str, dict[str, str | None]] = {}
    for file_name, columns in mapping_section.items():
        if not isinstance(columns, dict):
            raise ValueError(
                f"Mapping for '{file_name}' must be an object of source-to-output names."
            )
        overrides[str(file_name)] = {
            str(source): (None if target in (None, "") else str(target))
            for source, target in columns.items()
        }

    ignored: dict[str, list[str]] = {}
    ignored_section = raw.get("ignore", {})
    if ignored_section:
        if not isinstance(ignored_section, dict):
            raise ValueError("The mapping file's 'ignore' value must be an object.")
        for file_name, columns in ignored_section.items():
            if not isinstance(columns, list) or not all(
                isinstance(column, str) for column in columns
            ):
                raise ValueError(
                    f"'ignore' for '{file_name}' must be a list of column names."
                )
            ignored[str(file_name)] = columns
    return overrides, ignored


def _collect_input_paths(
    inputs: Sequence[str],
    output_dir: Path,
    *,
    recursive: bool,
) -> list[Path]:
    output_resolved = output_dir.resolve()
    collected: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen:
            return
        if resolved.is_relative_to(output_resolved):
            return
        if path.name.startswith(".") or path.name.startswith("~$"):
            return
        seen.add(resolved)
        collected.append(path)

    for raw in inputs:
        path = Path(raw).expanduser()
        if path.is_file():
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                raise ValueError(
                    f"Unsupported input file '{path.name}'. Use .csv or .xlsx files."
                )
            add(path)
            continue
        if path.is_dir():
            candidates = path.rglob("*") if recursive else path.iterdir()
            for candidate in sorted(candidates, key=lambda item: str(item).lower()):
                if not candidate.is_file():
                    continue
                if candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                    add(candidate)
            continue
        raise ValueError(f"Input path not found: {raw}")

    return collected


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _print_issues(issues, quiet: bool) -> None:
    for issue in issues:
        if issue.severity == "error":
            location = f" [{issue.file}]" if issue.file else ""
            print(f"Error{location}: {issue.message}", file=sys.stderr)
        elif not quiet:
            location = f" [{issue.file}]" if issue.file else ""
            print(f"Warning{location}: {issue.message}")


def _run_merge(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    output_dir = Path(args.output).expanduser()
    try:
        paths = _collect_input_paths(args.inputs, output_dir, recursive=args.recursive)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if not paths:
        print(
            "Error: no supported .csv or .xlsx input files were found. "
            "The output directory is ignored when scanning inputs.",
            file=sys.stderr,
        )
        return 1

    try:
        sheet_overrides = _parse_sheet_overrides(args.sheet)
        overrides, ignored = _load_mapping(args.mapping)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    read_options = ReadOptions(
        csv_delimiter=CSV_DELIMITER_OPTIONS[args.delimiter],
        csv_encoding=CSV_ENCODING_OPTIONS[args.encoding],
        csv_decimal=CSV_DECIMAL_OPTIONS[args.decimal],
        max_rows=args.max_rows,
    )
    files, issues = load_input_files(
        paths,
        read_options,
        sheet_overrides=sheet_overrides,
        max_files=args.max_files,
    )
    _print_issues(issues, args.quiet)
    failed_issues = [issue for issue in issues if issue.severity == "error"]
    if failed_issues and not args.skip_invalid:
        print(
            "Processing stopped because one or more input files failed validation. "
            "Use --skip-invalid to process the readable files and receive exit code 3.",
            file=sys.stderr,
        )
        return 1
    if not files:
        print("Error: no readable input files remain.", file=sys.stderr)
        return 1

    total_issue = check_total_rows(files, MAX_TOTAL_ROWS)
    if total_issue:
        print(f"Error: {total_issue.message}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"MergeMate {APP_VERSION}")
        print(f"Read {len(files)} file(s):")
        for loaded in files:
            sheet = f", worksheet '{loaded.sheet_name}'" if loaded.sheet_name else ""
            print(
                f"  - {loaded.display_name}: {loaded.row_count:,} rows, "
                f"{loaded.column_count} columns{sheet}"
            )

    try:
        plan = build_mapping_plan(files, overrides=overrides, ignored_columns=ignored)
    except MergeMateError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        differences = plan.header_differences()
        if differences:
            print(f"Header differences normalized: {len(differences)}")
        if plan.missing_columns_by_file:
            print("Missing columns detected:")
            for file_name, columns in plan.missing_columns_by_file.items():
                print(f"  - {file_name}: {', '.join(columns)}")
        if plan.ignored_columns_by_file:
            print("Ignored source columns:")
            for file_name, columns in plan.ignored_columns_by_file.items():
                print(f"  - {file_name}: {', '.join(columns)}")

    duplicate_mode = {"keep-all": "keep_all", "exact": "exact", "keys": "keys"}[
        args.duplicates
    ]
    options = ConsolidationOptions(
        missing_column_strategy=args.missing_columns,
        duplicate_mode=duplicate_mode,
        duplicate_key_columns=_split_csv_list(args.key_columns),
        duplicate_keep=args.keep,
        source_column=args.source_column.strip() or DEFAULT_SOURCE_COLUMN,
        trim_columns=_split_csv_list(args.trim),
        date_columns=_split_csv_list(args.parse_date),
        numeric_columns=_split_csv_list(args.numeric),
    )

    try:
        result = consolidate(files, plan, options)
    except MergeMateError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    failed_records = [
        {"name": issue.file or "unknown", "code": issue.code, "message": issue.message}
        for issue in failed_issues
    ]
    base_name = make_output_base_name()
    report = build_report(
        result,
        files,
        issues=issues,
        failed_files=failed_records,
        status="partial" if failed_records else "success",
    )
    try:
        written = export_all(
            result,
            report,
            output_dir,
            base_name,
            report_formats=args.report_format,
        )
    except MergeMateError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        f"Consolidated {result.output_row_count:,} rows and "
        f"{result.output_column_count} columns from {len(files)} file(s)."
    )
    for key, path in written.items():
        print(f"  {key}: {_display_path(path)}")
    if result.duplicates.get("rows_removed"):
        print(f"Duplicate rows removed: {result.duplicates['rows_removed']:,}")
    if failed_records:
        print(
            f"Partial run: {len(failed_records)} input file(s) were skipped.",
            file=sys.stderr,
        )
        return 3
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "merge":
        try:
            return _run_merge(args, parser)
        except KeyboardInterrupt:
            print("\nCancelled.", file=sys.stderr)
            return 130
        except Exception as exc:  # unexpected errors should still be actionable
            print(f"Unexpected error: {exc}", file=sys.stderr)
            return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

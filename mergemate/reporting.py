"""Build and serialize the MergeMate processing report."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

from mergemate.config import APP_NAME, APP_VERSION
from mergemate.consolidation import ConsolidationResult
from mergemate.file_readers import LoadedFile
from mergemate.validation import ValidationIssue, issues_to_dicts


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _failed_file_records(
    failed_files: Iterable[dict[str, Any] | ValidationIssue],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in failed_files:
        if isinstance(item, ValidationIssue):
            records.append(
                {
                    "name": item.file or "unknown",
                    "code": item.code,
                    "message": item.message,
                }
            )
        else:
            records.append(dict(item))
    return records


def build_report(
    result: ConsolidationResult,
    files: list[LoadedFile],
    *,
    issues: Iterable[ValidationIssue] = (),
    failed_files: Iterable[dict[str, Any] | ValidationIssue] = (),
    output_files: dict[str, str] | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Create a JSON-serializable report without copying data rows."""
    plan = result.plan
    output_files = output_files or {}
    failed_records = _failed_file_records(failed_files)

    all_issues = list(issues)
    for warning in plan.warnings:
        all_issues.append(
            ValidationIssue(
                severity="warning",
                code="mapping_warning",
                message=warning,
            )
        )
    all_issues.extend(result.issues)

    if status is None:
        status = "partial" if failed_records else "success"

    conversion_issues = [
        conversion
        for conversion in result.conversions
        if conversion.get("invalid_values", 0)
    ]
    detected = {
        "exact_duplicate_rows": result.duplicates.get("exact_duplicates_detected", 0),
        "missing_columns": plan.missing_columns_by_file,
        "file_specific_columns": plan.file_specific_columns_by_file,
        "header_differences": plan.header_differences(),
        "conversion_issues": conversion_issues,
        "suggestions": plan.suggestions(),
    }
    applied = {
        "missing_column_strategy": result.options.missing_column_strategy,
        "missing_columns_filled": {
            file: columns
            for file, columns in result.missing_filled_by_file.items()
            if columns
        },
        "excluded_columns": {
            file: columns
            for file, columns in result.excluded_columns_by_file.items()
            if columns
        },
        "duplicate_removal": {
            "mode": result.options.duplicate_mode,
            "keep": result.options.duplicate_keep,
            "key_columns": list(result.options.duplicate_key_columns),
            "rows_removed": result.duplicates.get("rows_removed", 0),
        },
        "trimmed_columns": list(result.options.trim_columns),
        "date_columns_parsed": list(result.options.date_columns),
        "numeric_columns_converted": list(result.options.numeric_columns),
        "ignored_columns": plan.ignored_columns_by_file,
    }

    return {
        "tool": {"name": APP_NAME, "version": APP_VERSION},
        "generated_at": utc_now_iso(),
        "status": status,
        "inputs": {
            "processed_count": len(files),
            "failed_count": len(failed_records),
            "files": [file.summary() for file in files],
            "failed_files": failed_records,
        },
        "output": {
            "rows": result.output_row_count,
            "columns": result.output_column_count,
            "source_counts": result.output_source_counts,
            "files": output_files,
        },
        "columns": {
            "output_columns": list(result.output_columns),
            "common_columns": list(plan.common_columns),
            "missing_columns": plan.missing_columns_by_file,
            "file_specific_columns": plan.file_specific_columns_by_file,
            "ignored_columns": plan.ignored_columns_by_file,
            "mapping": plan.mapping_rows(),
        },
        "options": asdict(result.options),
        "detected": detected,
        "applied": applied,
        "duplicates": result.duplicates,
        "conversions": result.conversions,
        "validation_issues": issues_to_dicts(all_issues),
        "timing": {
            "processing_seconds": round(result.processing_seconds, 4),
            "report_generated_at": utc_now_iso(),
        },
    }


def report_to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, default=str)


def _flatten(value: Any, prefix: str, rows: list[tuple[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten(child, child_prefix, rows)
    elif isinstance(value, list):
        rows.append((prefix, json.dumps(value, ensure_ascii=False, default=str)))
    else:
        rows.append((prefix, value))


def report_to_csv(report: dict[str, Any]) -> str:
    """Flatten the report into a two-column CSV for quick inspection."""
    rows: list[tuple[str, Any]] = []
    _flatten(report, "", rows)
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["field", "value"])
    for field, value in rows:
        writer.writerow([field, "" if value is None else value])
    return buffer.getvalue()


def write_report_json(report: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_to_json(report), encoding="utf-8")
    return path


def write_report_csv(report: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_to_csv(report), encoding="utf-8")
    return path

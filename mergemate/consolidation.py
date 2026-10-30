"""Consolidation engine shared by the Streamlit app and the CLI."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from mergemate.column_mapping import ColumnMappingPlan
from mergemate.config import (
    DEFAULT_SOURCE_COLUMN,
    DUPLICATE_KEEP,
    DUPLICATE_MODES,
    MISSING_STRATEGIES,
)
from mergemate.exceptions import ConsolidationError, IncompatibleFilesError
from mergemate.file_readers import LoadedFile
from mergemate.validation import ValidationIssue


@dataclass
class ConsolidationOptions:
    """User-selected rules for one consolidation run."""

    missing_column_strategy: str = "blank"
    duplicate_mode: str = "keep_all"
    duplicate_key_columns: tuple[str, ...] = ()
    duplicate_keep: str = "first"
    source_column: str = DEFAULT_SOURCE_COLUMN
    trim_columns: tuple[str, ...] = ()
    date_columns: tuple[str, ...] = ()
    numeric_columns: tuple[str, ...] = ()


@dataclass
class ConsolidationResult:
    """The merged data plus everything needed for a report or preview."""

    dataframe: pd.DataFrame
    plan: ColumnMappingPlan
    options: ConsolidationOptions
    input_row_counts: dict[str, int]
    output_source_counts: dict[str, int]
    output_columns: list[str]
    duplicates: dict[str, Any]
    conversions: list[dict[str, Any]] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    missing_filled_by_file: dict[str, list[str]] = field(default_factory=dict)
    excluded_columns_by_file: dict[str, list[str]] = field(default_factory=dict)
    processing_seconds: float = 0.0

    @property
    def output_row_count(self) -> int:
        return len(self.dataframe)

    @property
    def output_column_count(self) -> int:
        return len(self.dataframe.columns)


def _validate_options(options: ConsolidationOptions, plan: ColumnMappingPlan) -> None:
    if options.missing_column_strategy not in MISSING_STRATEGIES:
        raise ConsolidationError(
            f"Unknown missing-column strategy '{options.missing_column_strategy}'."
        )
    if options.duplicate_mode not in DUPLICATE_MODES:
        raise ConsolidationError(f"Unknown duplicate mode '{options.duplicate_mode}'.")
    if options.duplicate_keep not in DUPLICATE_KEEP:
        raise ConsolidationError(
            f"Unknown duplicate keep strategy '{options.duplicate_keep}'."
        )
    if options.duplicate_mode == "keys" and not options.duplicate_key_columns:
        raise ConsolidationError(
            "Choose at least one key column when removing duplicates by key."
        )
    if not options.source_column.strip():
        raise ConsolidationError("The source-file column name cannot be blank.")
    if options.source_column in plan.canonical_columns:
        raise ConsolidationError(
            f"Source column '{options.source_column}' conflicts with an output column. "
            "Choose another source-column name."
        )
    if options.duplicate_mode == "keys":
        unknown_keys = [
            column
            for column in options.duplicate_key_columns
            if column not in plan.canonical_columns
        ]
        if unknown_keys:
            raise ConsolidationError(
                "Unknown duplicate key column(s): " + ", ".join(unknown_keys) + "."
            )
    for label, columns in (
        ("trim", options.trim_columns),
        ("date", options.date_columns),
        ("numeric", options.numeric_columns),
    ):
        unknown = [column for column in columns if column not in plan.canonical_columns]
        if unknown:
            raise ConsolidationError(
                f"Unknown {label} column(s): " + ", ".join(unknown) + "."
            )
    overlap = set(options.date_columns) & set(options.numeric_columns)
    if overlap:
        raise ConsolidationError(
            "A column cannot be parsed as both a date and a number: "
            + ", ".join(sorted(overlap))
            + "."
        )


def _apply_mapping(
    files: list[LoadedFile],
    plan: ColumnMappingPlan,
    options: ConsolidationOptions,
) -> tuple[pd.DataFrame, list[str], dict[str, list[str]], dict[str, list[str]]]:
    if options.missing_column_strategy == "reject" and plan.has_missing_columns:
        details = "; ".join(
            f"{file}: {', '.join(columns)}"
            for file, columns in plan.missing_columns_by_file.items()
        )
        raise IncompatibleFilesError(
            "Files have missing columns and the selected strategy rejects them. " + details
        )

    if options.missing_column_strategy == "exclude":
        output_columns = list(plan.common_columns)
        if not output_columns:
            raise IncompatibleFilesError(
                "No column exists in every file. Choose 'fill missing columns with blanks' "
                "or remove incompatible files."
            )
    else:
        output_columns = list(plan.canonical_columns)

    if not output_columns:
        raise IncompatibleFilesError("The output schema has no columns.")

    frames: list[pd.DataFrame] = []
    missing_filled: dict[str, list[str]] = {}
    excluded_columns: dict[str, list[str]] = {}

    for loaded in files:
        mapping = plan.file_mappings[loaded.display_name]
        selected = [
            source
            for source in loaded.columns
            if source in mapping.source_to_output
            and mapping.source_to_output[source] in output_columns
        ]
        if not selected:
            raise IncompatibleFilesError(
                f"'{loaded.display_name}' has no columns in common with the output schema."
            )
        frame = loaded.dataframe.loc[:, selected].copy()
        frame = frame.rename(
            columns={source: mapping.source_to_output[source] for source in selected}
        )
        missing_filled[loaded.display_name] = [
            column for column in output_columns if column not in frame.columns
        ]
        excluded_columns[loaded.display_name] = [
            column
            for column in mapping.mapped_output_columns
            if column not in output_columns
        ]
        frame = frame.reindex(columns=output_columns)
        frame.insert(0, options.source_column, loaded.display_name)
        frames.append(frame)

    consolidated = pd.concat(frames, ignore_index=True, sort=False)
    return consolidated, output_columns, missing_filled, excluded_columns


def _trim_columns(
    df: pd.DataFrame,
    columns: tuple[str, ...],
    conversions: list[dict[str, Any]],
    issues: list[ValidationIssue],
) -> None:
    for column in columns:
        series = df[column]
        non_null = series.dropna()
        non_text = [
            value for value in non_null.head(1_000) if not isinstance(value, str)
        ]
        if non_text:
            raise ConsolidationError(
                f"Column '{column}' contains non-text values; trimming is only "
                "available for text columns."
            )
        trimmed = series.map(
            lambda value: value.strip() if isinstance(value, str) else value
        )
        changed = int((trimmed.fillna("") != series.fillna("")).sum())
        df[column] = trimmed
        conversions.append(
            {
                "operation": "trim_whitespace",
                "column": column,
                "changed_values": changed,
                "invalid_values": 0,
            }
        )
        if changed:
            issues.append(
                ValidationIssue(
                    severity="info",
                    code="trim_applied",
                    message=f"Trimmed whitespace in {changed:,} value(s) in '{column}'.",
                )
            )


def _parse_dates(
    df: pd.DataFrame,
    columns: tuple[str, ...],
    conversions: list[dict[str, Any]],
    issues: list[ValidationIssue],
) -> None:
    for column in columns:
        series = df[column]
        if pd.api.types.is_numeric_dtype(series):
            raise ConsolidationError(
                f"Column '{column}' is numeric; choose a text or date column for date parsing."
            )
        if pd.api.types.is_datetime64_any_dtype(series):
            conversions.append(
                {
                    "operation": "parse_date",
                    "column": column,
                    "changed_values": 0,
                    "invalid_values": 0,
                    "already_datetime": True,
                }
            )
            continue
        parsed = pd.to_datetime(series, errors="coerce", format="mixed")
        invalid = int((series.notna() & parsed.isna()).sum())
        df[column] = parsed
        conversions.append(
            {
                "operation": "parse_date",
                "column": column,
                "changed_values": int(series.notna().sum()) - invalid,
                "invalid_values": invalid,
            }
        )
        if invalid:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="date_conversion",
                    message=(
                        f"{invalid:,} value(s) in '{column}' could not be parsed as dates "
                        "and were left blank. Rows were kept."
                    ),
                )
            )


def _convert_numeric(
    df: pd.DataFrame,
    columns: tuple[str, ...],
    conversions: list[dict[str, Any]],
    issues: list[ValidationIssue],
) -> None:
    for column in columns:
        series = df[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            raise ConsolidationError(
                f"Column '{column}' is a date column; choose a text or numeric column "
                "for numeric conversion."
            )
        if pd.api.types.is_numeric_dtype(series):
            conversions.append(
                {
                    "operation": "convert_numeric",
                    "column": column,
                    "changed_values": 0,
                    "invalid_values": 0,
                    "already_numeric": True,
                }
            )
            continue
        converted = pd.to_numeric(series, errors="coerce")
        invalid = int((series.notna() & converted.isna()).sum())
        df[column] = converted
        conversions.append(
            {
                "operation": "convert_numeric",
                "column": column,
                "changed_values": int(series.notna().sum()) - invalid,
                "invalid_values": invalid,
            }
        )
        if invalid:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="numeric_conversion",
                    message=(
                        f"{invalid:,} value(s) in '{column}' could not be converted to "
                        "numbers and were left blank. Rows were kept."
                    ),
                )
            )


def _deduplicate(
    df: pd.DataFrame,
    options: ConsolidationOptions,
    issues: list[ValidationIssue],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    data_columns = [column for column in df.columns if column != options.source_column]
    exact_mask = df.duplicated(subset=data_columns, keep="first")
    exact_detected = int(exact_mask.sum())
    before = len(df)
    removed = 0

    if options.duplicate_mode == "exact":
        df = df.drop_duplicates(subset=data_columns, keep="first").reset_index(drop=True)
        removed = before - len(df)
    elif options.duplicate_mode == "keys":
        missing_keys = [
            column
            for column in options.duplicate_key_columns
            if column not in df.columns
        ]
        if missing_keys:
            raise ConsolidationError(
                "Duplicate key column(s) are not present in the output schema: "
                + ", ".join(missing_keys)
                + "."
            )
        df = df.drop_duplicates(
            subset=list(options.duplicate_key_columns),
            keep=options.duplicate_keep,
        ).reset_index(drop=True)
        removed = before - len(df)

    duplicates = {
        "mode": options.duplicate_mode,
        "keep": options.duplicate_keep if options.duplicate_mode == "keys" else "first",
        "key_columns": list(options.duplicate_key_columns)
        if options.duplicate_mode == "keys"
        else [],
        "exact_duplicates_detected": exact_detected,
        "rows_before": before,
        "rows_removed": removed,
        "rows_after": len(df),
    }
    if removed:
        issues.append(
            ValidationIssue(
                severity="info",
                code="duplicates_removed",
                message=(
                    f"Removed {removed:,} duplicate row(s) using the selected "
                    f"'{options.duplicate_mode}' strategy."
                ),
            )
        )
    return df, duplicates


def consolidate(
    files: list[LoadedFile],
    plan: ColumnMappingPlan,
    options: ConsolidationOptions | None = None,
) -> ConsolidationResult:
    """Apply the mapping, optional normalization, and duplicate policy."""
    if not files:
        raise ConsolidationError("At least one readable input file is required.")
    options = options or ConsolidationOptions()
    _validate_options(options, plan)

    started = time.perf_counter()
    consolidated, output_columns, missing_filled, excluded_columns = _apply_mapping(
        files, plan, options
    )

    conversions: list[dict[str, Any]] = []
    issues: list[ValidationIssue] = []

    for column in (
        options.trim_columns + options.date_columns + options.numeric_columns
    ):
        if column not in consolidated.columns:
            raise ConsolidationError(
                f"Column '{column}' is not part of the output schema under the "
                "selected missing-column strategy."
            )

    _trim_columns(consolidated, options.trim_columns, conversions, issues)
    _parse_dates(consolidated, options.date_columns, conversions, issues)
    _convert_numeric(consolidated, options.numeric_columns, conversions, issues)

    consolidated, duplicates = _deduplicate(consolidated, options, issues)

    source_counts = {
        str(name): int(count)
        for name, count in consolidated[options.source_column]
        .value_counts()
        .sort_index()
        .items()
    }
    input_row_counts = {file.display_name: file.row_count for file in files}
    elapsed = time.perf_counter() - started

    return ConsolidationResult(
        dataframe=consolidated,
        plan=plan,
        options=options,
        input_row_counts=input_row_counts,
        output_source_counts=source_counts,
        output_columns=output_columns,
        duplicates=duplicates,
        conversions=conversions,
        issues=issues,
        missing_filled_by_file=missing_filled,
        excluded_columns_by_file=excluded_columns,
        processing_seconds=elapsed,
    )

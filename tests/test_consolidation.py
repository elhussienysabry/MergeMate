from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from mergemate.column_mapping import build_mapping_plan
from mergemate.consolidation import ConsolidationOptions, consolidate
from mergemate.exceptions import ConsolidationError, IncompatibleFilesError
from mergemate.file_readers import load_input_files


def test_missing_columns_filled_blank(pipeline_result) -> None:
    files, _, _, result = pipeline_result

    assert result.output_row_count == 6
    assert result.output_column_count == 6
    assert result.output_columns == [
        "customer_name",
        "amount",
        "date",
        "region",
        "notes",
    ]
    assert "date" in result.missing_filled_by_file["c.xlsx"]
    assert "notes" in result.missing_filled_by_file["c.xlsx"]
    dan = result.dataframe[result.dataframe["customer_name"] == "Dan"].iloc[0]
    assert pd.isna(dan["date"])
    assert pd.isna(dan["notes"])
    assert set(result.output_source_counts) == {file.display_name for file in files}


def test_missing_columns_excluded(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)

    result = consolidate(
        files,
        plan,
        ConsolidationOptions(missing_column_strategy="exclude"),
    )

    assert result.output_columns == ["customer_name", "amount", "region"]
    assert "date" not in result.dataframe.columns
    assert "notes" not in result.dataframe.columns
    assert result.excluded_columns_by_file["a.csv"] == ["date", "notes"]


def test_missing_columns_reject(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)

    with pytest.raises(IncompatibleFilesError, match="rejects"):
        consolidate(
            files,
            plan,
            ConsolidationOptions(missing_column_strategy="reject"),
        )


def test_keep_all_does_not_remove_duplicates(pipeline_result) -> None:
    _, _, _, result = pipeline_result

    assert result.output_row_count == 6
    assert result.duplicates["exact_duplicates_detected"] == 2
    assert result.duplicates["rows_removed"] == 0
    assert result.duplicates["mode"] == "keep_all"


def test_exact_duplicate_removal_ignores_source_column(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)

    result = consolidate(
        files,
        plan,
        ConsolidationOptions(duplicate_mode="exact"),
    )

    assert result.duplicates["exact_duplicates_detected"] == 2
    assert result.duplicates["rows_removed"] == 2
    assert result.output_row_count == 4
    assert result.output_source_counts == {
        "a.csv": 2,
        "b.csv": 1,
        "c.xlsx": 1,
    }
    bob_rows = result.dataframe[result.dataframe["customer_name"] == "Bob"]
    assert len(bob_rows) == 1
    assert bob_rows.iloc[0]["Source_File"] == "a.csv"


def test_key_duplicate_removal_keep_first(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)

    result = consolidate(
        files,
        plan,
        ConsolidationOptions(
            duplicate_mode="keys",
            duplicate_key_columns=("customer_name",),
            duplicate_keep="first",
        ),
    )

    assert result.output_row_count == 4
    assert result.duplicates["rows_removed"] == 2
    assert result.duplicates["key_columns"] == ["customer_name"]
    assert result.output_source_counts["a.csv"] == 2
    assert result.output_source_counts["b.csv"] == 1


def test_key_duplicate_removal_keep_last(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)

    result = consolidate(
        files,
        plan,
        ConsolidationOptions(
            duplicate_mode="keys",
            duplicate_key_columns=("customer_name",),
            duplicate_keep="last",
        ),
    )

    assert result.output_row_count == 4
    bob = result.dataframe[result.dataframe["customer_name"] == "Bob"].iloc[0]
    alice = result.dataframe[result.dataframe["customer_name"] == "Alice"].iloc[0]
    assert bob["Source_File"] == "b.csv"
    assert alice["Source_File"] == "a.csv"


def test_type_normalization_reports_invalid_values(tmp_path: Path) -> None:
    path = tmp_path / "types.csv"
    path.write_text(
        "When,Value,Text\n"
        "2024-01-01,10,  alpha  \n"
        "not-a-date,oops,  beta  \n",
        encoding="utf-8",
    )
    files, _ = load_input_files([path])
    plan = build_mapping_plan(files)

    result = consolidate(
        files,
        plan,
        ConsolidationOptions(
            date_columns=("when",),
            numeric_columns=("value",),
            trim_columns=("text",),
        ),
    )

    assert result.output_row_count == 2
    assert str(result.dataframe.loc[1, "when"]) == "NaT"
    assert pd.isna(result.dataframe.loc[1, "value"])
    assert result.dataframe.loc[0, "text"] == "alpha"
    conversions = {item["operation"]: item for item in result.conversions}
    assert conversions["parse_date"]["invalid_values"] == 1
    assert conversions["convert_numeric"]["invalid_values"] == 1
    assert conversions["trim_whitespace"]["changed_values"] == 2
    codes = {issue.code for issue in result.issues}
    assert {"date_conversion", "numeric_conversion", "trim_applied"} <= codes


def test_trim_rejects_non_text_column(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)

    with pytest.raises(ConsolidationError, match="non-text"):
        consolidate(
            files,
            plan,
            ConsolidationOptions(trim_columns=("amount",)),
        )


def test_parse_date_rejects_numeric_column(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)

    with pytest.raises(ConsolidationError, match="numeric"):
        consolidate(
            files,
            plan,
            ConsolidationOptions(date_columns=("amount",)),
        )


def test_invalid_duplicate_options(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)

    with pytest.raises(ConsolidationError, match="at least one key"):
        consolidate(
            files,
            plan,
            ConsolidationOptions(duplicate_mode="keys"),
        )

    with pytest.raises(ConsolidationError, match="Unknown duplicate key"):
        consolidate(
            files,
            plan,
            ConsolidationOptions(
                duplicate_mode="keys",
                duplicate_key_columns=("missing",),
            ),
        )


def test_source_column_collision(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)

    with pytest.raises(ConsolidationError, match="conflicts"):
        consolidate(files, plan, ConsolidationOptions(source_column="amount"))


def test_date_and_numeric_overlap_rejected(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)

    with pytest.raises(ConsolidationError, match="both a date and a number"):
        consolidate(
            files,
            plan,
            ConsolidationOptions(
                date_columns=("date",),
                numeric_columns=("date",),
            ),
        )


def test_empty_file_list_rejected(tmp_path: Path) -> None:
    path = tmp_path / "one.csv"
    path.write_text("a\n1\n", encoding="utf-8")
    files, _ = load_input_files([path])
    plan = build_mapping_plan(files)

    with pytest.raises(ConsolidationError, match="At least one"):
        consolidate([], plan)


def test_deterministic_processing(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)
    options = ConsolidationOptions(
        duplicate_mode="exact",
        date_columns=("date",),
    )

    first = consolidate(files, plan, options)
    second = consolidate(files, plan, options)

    pd.testing.assert_frame_equal(first.dataframe, second.dataframe)
    assert first.duplicates == second.duplicates
    assert first.conversions == second.conversions
    assert first.output_source_counts == second.output_source_counts


def test_key_columns_excluded_by_missing_policy(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)

    with pytest.raises(ConsolidationError, match="not present in the output schema"):
        consolidate(
            files,
            plan,
            ConsolidationOptions(
                missing_column_strategy="exclude",
                duplicate_mode="keys",
                duplicate_key_columns=("date",),
            ),
        )

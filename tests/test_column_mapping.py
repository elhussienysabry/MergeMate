from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from mergemate.column_mapping import build_mapping_plan, normalize_column_name
from mergemate.exceptions import MappingError
from mergemate.file_readers import load_input_files


def test_normalize_column_name_variants() -> None:
    assert normalize_column_name(" Customer Name ") == "customer_name"
    assert normalize_column_name("customer_name") == "customer_name"
    assert normalize_column_name("Customer_Name") == "customer_name"
    assert normalize_column_name("CO2 (tCO2)") == "co2_tco2"
    assert normalize_column_name("Lagging Current Reactive Power (kVarh)") == (
        "lagging_current_reactive_power_kvarh"
    )


def test_normalize_empty_name_raises() -> None:
    with pytest.raises(MappingError, match="cannot be normalized"):
        normalize_column_name("   ")


def test_auto_mapping_detects_equivalent_headers(
    pipeline_files: dict[str, Path],
) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))

    plan = build_mapping_plan(files)

    assert plan.canonical_columns[:3] == ["customer_name", "amount", "date"]
    assert plan.file_mappings["a.csv"].source_to_output["Customer Name"] == "customer_name"
    assert plan.file_mappings["b.csv"].source_to_output["customer_name"] == "customer_name"
    assert plan.file_mappings["c.xlsx"].source_to_output["Customer_Name"] == "customer_name"
    assert plan.missing_columns_by_file == {"c.xlsx": ["date", "notes"]}
    assert "notes" in plan.file_specific_columns_by_file["a.csv"]
    assert plan.common_columns == ["customer_name", "amount", "region"]


def test_explicit_mapping_merges_different_header_names(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    first.write_text("Customer Name,Amount\nAlice,10\n", encoding="utf-8")
    second = tmp_path / "second.csv"
    second.write_text("CustomerName,Amount\nBob,20\n", encoding="utf-8")
    files, _ = load_input_files([first, second])

    auto_plan = build_mapping_plan(files)
    assert auto_plan.common_columns == ["amount"]
    assert "customername" in auto_plan.file_specific_columns_by_file["second.csv"]

    plan = build_mapping_plan(
        files,
        overrides={"second.csv": {"CustomerName": "customer_name"}},
    )

    assert plan.common_columns == ["customer_name", "amount"]
    assert plan.file_mappings["second.csv"].source_to_output["CustomerName"] == (
        "customer_name"
    )
    assert plan.header_differences()


def test_ignored_column_is_removed_from_plan(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))

    plan = build_mapping_plan(
        files,
        ignored_columns={"a.csv": ["Notes"], "b.csv": ["Notes"]},
    )

    assert plan.file_mappings["a.csv"].source_to_output.get("Notes") is None
    assert "notes" not in plan.canonical_columns
    assert plan.ignored_columns_by_file == {"a.csv": ["Notes"], "b.csv": ["Notes"]}


def test_duplicate_normalized_headers_raise(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.csv"
    path.write_text("Customer Name,customer_name\nA,B\n", encoding="utf-8")
    files, _ = load_input_files([path])

    with pytest.raises(MappingError, match="both normalize"):
        build_mapping_plan(files)


def test_mapping_rejects_unknown_file(tmp_path: Path) -> None:
    path = tmp_path / "one.csv"
    path.write_text("a\n1\n", encoding="utf-8")
    files, _ = load_input_files([path])

    with pytest.raises(MappingError, match="unknown file"):
        build_mapping_plan(files, overrides={"missing.csv": {"a": "b"}})


def test_mapping_rejects_unknown_column(tmp_path: Path) -> None:
    path = tmp_path / "one.csv"
    path.write_text("a\n1\n", encoding="utf-8")
    files, _ = load_input_files([path])

    with pytest.raises(MappingError, match="not present"):
        build_mapping_plan(files, overrides={"one.csv": {"missing": "a"}})


def test_mapping_rejects_two_sources_to_same_target(tmp_path: Path) -> None:
    path = tmp_path / "one.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    files, _ = load_input_files([path])

    with pytest.raises(MappingError, match="More than one column"):
        build_mapping_plan(files, overrides={"one.csv": {"b": "a"}})


def test_mapping_rows_include_ignored_status(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files, ignored_columns={"a.csv": ["Notes"]})

    rows = plan.mapping_rows()
    note_row = next(row for row in rows if row["file"] == "a.csv" and row["source_header"] == "Notes")

    assert note_row["status"] == "ignored"
    assert note_row["output_column"] == ""


def test_mapping_suggestions_are_not_auto_applied(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    first.write_text("CustomerName,Amount\nAlice,10\n", encoding="utf-8")
    second = tmp_path / "second.csv"
    second.write_text("customer_name,Amount\nBob,20\n", encoding="utf-8")
    files, _ = load_input_files([first, second])

    plan = build_mapping_plan(files)

    assert plan.file_mappings["first.csv"].source_to_output["CustomerName"] == (
        "customername"
    )
    assert "customer_name" not in plan.file_mappings["first.csv"].source_to_output.values()
    assert plan.common_columns == ["amount"]


def test_plan_rejects_empty_file_list() -> None:
    with pytest.raises(MappingError, match="At least one"):
        build_mapping_plan([])


def test_plan_has_deterministic_column_order(pipeline_files: dict[str, Path]) -> None:
    files, _ = load_input_files(list(pipeline_files.values()))
    first = build_mapping_plan(files)
    second = build_mapping_plan(files)

    assert first.canonical_columns == second.canonical_columns
    assert first.mapping_rows() == second.mapping_rows()
    assert isinstance(pd.DataFrame(first.mapping_rows()), pd.DataFrame)

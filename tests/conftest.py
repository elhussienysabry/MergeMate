from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from mergemate.column_mapping import build_mapping_plan
from mergemate.consolidation import ConsolidationOptions, consolidate
from mergemate.file_readers import load_input_files


@pytest.fixture
def pipeline_files(tmp_path: Path) -> dict[str, Path]:
    """Three small files with mixed formats and deliberate differences."""
    a = tmp_path / "a.csv"
    a.write_text(
        "Customer Name,Amount,Date,Region,Notes\n"
        "Alice,10.5,2024-01-01,North,first\n"
        "Bob,20.0,2024-01-02,South,repeat\n"
        "Alice,10.5,2024-01-01,North,first\n",
        encoding="utf-8",
    )

    b = tmp_path / "b.csv"
    b.write_text(
        "customer_name,Amount,Date,Region,Notes\n"
        "Carol,30.0,2024-02-01,West,west\n"
        "Bob,20.0,2024-01-02,South,repeat\n",
        encoding="utf-8",
    )

    c = tmp_path / "c.xlsx"
    with pd.ExcelWriter(c, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "Customer_Name": ["Dan"],
                "Amount": [40.0],
                "Region": ["East"],
            }
        ).to_excel(writer, index=False, sheet_name="Records")
    return {"a": a, "b": b, "c": c}


@pytest.fixture
def pipeline_result(pipeline_files: dict[str, Path]):
    files, issues = load_input_files(list(pipeline_files.values()))
    plan = build_mapping_plan(files)
    result = consolidate(
        files,
        plan,
        ConsolidationOptions(duplicate_mode="keep_all"),
    )
    return files, issues, plan, result

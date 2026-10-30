"""Regenerate the documented demonstration inputs from the fixed source file.

The source is the official UCI Steel Industry Energy Consumption CSV. The
script only splits records by calendar quarter and applies documented header
variations. It adds one exact duplicate record and removes one optional
column from the fourth file to exercise the consolidation workflow.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE = PROJECT_ROOT / "data" / "source" / "Steel_industry_data.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "sample_inputs"

QUARTERS = [
    {
        "file": "steel_energy_2018_q1.csv",
        "label": "2018 Q1",
        "start": "2018-01-01",
        "end": "2018-04-01",
        "format": "csv",
        "headers": [
            "Date",
            "Usage kWh",
            "Lagging Current Reactive Power (kVarh)",
            "Leading Current Reactive Power (kVarh)",
            "CO2 (tCO2)",
            "Lagging Current Power Factor",
            "Leading Current Power Factor",
            "NSM",
            "Week Status",
            "Day of Week",
            "Load Type",
        ],
        "header_style": "readable spaced headers",
        "missing": [],
    },
    {
        "file": "steel_energy_2018_q2.xlsx",
        "label": "2018 Q2",
        "start": "2018-04-01",
        "end": "2018-07-01",
        "format": "xlsx",
        "headers": [
            "date",
            "Usage_kWh",
            "Lagging_Current_Reactive.Power_kVarh",
            "Leading_Current_Reactive_Power_kVarh",
            "CO2(tCO2)",
            "Lagging_Current_Power_Factor",
            "Leading_Current_Power_Factor",
            "NSM",
            "Week_Status",
            "Day_of_week",
            "Load_Type",
        ],
        "header_style": "original-style mixed headers",
        "missing": [],
    },
    {
        "file": "steel_energy_2018_q3.csv",
        "label": "2018 Q3",
        "start": "2018-07-01",
        "end": "2018-10-01",
        "format": "csv",
        "headers": [
            "date",
            "usage_kwh",
            "lagging_current_reactive_power_kvarh",
            "leading_current_reactive_power_kvarh",
            "co2_tco2",
            "lagging_current_power_factor",
            "leading_current_power_factor",
            "nsm",
            "week_status",
            "day_of_week",
            "load_type",
        ],
        "header_style": "snake_case headers",
        "missing": [],
    },
    {
        "file": "steel_energy_2018_q4.xlsx",
        "label": "2018 Q4",
        "start": "2018-10-01",
        "end": "2019-01-01",
        "format": "xlsx",
        "headers": [
            "Date",
            "Usage (kWh)",
            "Lagging Current Reactive Power (kVarh)",
            "Leading Current Reactive Power (kVarh)",
            "Lagging Current Power Factor",
            "Leading Current Power Factor",
            "NSM",
            "Week Status",
            "Day of Week",
            "Load Type",
        ],
        "header_style": "spaced headers with one optional column omitted",
        "missing": ["CO2 (tCO2)"],
    },
]

SOURCE_COLUMNS = [
    "date",
    "Usage_kWh",
    "Lagging_Current_Reactive.Power_kVarh",
    "Leading_Current_Reactive_Power_kVarh",
    "CO2(tCO2)",
    "Lagging_Current_Power_Factor",
    "Leading_Current_Power_Factor",
    "NSM",
    "WeekStatus",
    "Day_of_week",
    "Load_Type",
]

# Q4 intentionally has no CO2 column. This is the subset used for that file.
Q4_SOURCE_COLUMNS = [column for column in SOURCE_COLUMNS if column != "CO2(tCO2)"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Source file not found: {SOURCE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    source = pd.read_csv(SOURCE)
    source["date"] = pd.to_datetime(source["date"], dayfirst=True)
    source = source[SOURCE_COLUMNS].sort_values("date").reset_index(drop=True)

    manifest_files = []
    for quarter in QUARTERS:
        start = pd.Timestamp(quarter["start"])
        end = pd.Timestamp(quarter["end"])
        subset = source[(source["date"] >= start) & (source["date"] < end)].copy()
        if subset.empty:
            raise SystemExit(f"No records found for {quarter['label']}.")

        source_columns = (
            Q4_SOURCE_COLUMNS if quarter["file"].endswith("q4.xlsx") else SOURCE_COLUMNS
        )
        subset = subset[source_columns].reset_index(drop=True)
        subset.columns = quarter["headers"]

        if quarter["file"].endswith("q4.xlsx"):
            # One documented exact duplicate for the duplicate-handling demo.
            subset = pd.concat([subset, subset.iloc[[0]]], ignore_index=True)

        # Keep the date representation consistent across CSV and XLSX inputs.
        # The values are the same timestamps; parsing is offered as an optional
        # normalization step in MergeMate.
        date_column = quarter["headers"][0]
        subset[date_column] = subset[date_column].dt.strftime("%Y-%m-%d %H:%M:%S")

        destination = OUTPUT_DIR / quarter["file"]
        if quarter["format"] == "csv":
            subset.to_csv(
                destination,
                index=False,
                sep=";",
                decimal=",",
                date_format="%Y-%m-%d %H:%M:%S",
                encoding="utf-8",
            )
        else:
            with pd.ExcelWriter(destination, engine="openpyxl") as writer:
                subset.to_excel(writer, index=False, sheet_name="Energy Data")

        manifest_files.append(
            {
                "file": quarter["file"],
                "quarter": quarter["label"],
                "date_start": quarter["start"],
                "date_end_exclusive": quarter["end"],
                "format": quarter["format"],
                "rows": int(len(subset)),
                "columns": int(len(subset.columns)),
                "header_style": quarter["header_style"],
                "csv_delimiter": "semicolon" if quarter["format"] == "csv" else None,
                "csv_decimal": "comma" if quarter["format"] == "csv" else None,
                "missing_column": quarter["missing"],
                "documented_duplicate_rows": 1 if quarter["file"].endswith("q4.xlsx") else 0,
                "sha256": sha256(destination),
            }
        )

    manifest = {
        "source_file": SOURCE.name,
        "source_sha256": sha256(SOURCE),
        "source_title": "Steel Industry Energy Consumption",
        "source_doi": "10.24432/C52G8C",
        "source_license": "CC BY 4.0",
        "download_date": "2026-10-28",
        "generation_note": (
            "Records are split deterministically by 2018 calendar quarter. "
            "Header labels are demonstration variations only; values are unchanged. "
            "Q4 contains one exact duplicate of its first record and omits the "
            "CO2(tCO2) column to exercise missing-column handling."
        ),
        "total_source_records": int(len(source)),
        "total_demo_records": int(sum(item["rows"] for item in manifest_files)),
        "files": manifest_files,
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(manifest_files)} demo files to {OUTPUT_DIR}")
    print(f"Total demo records: {manifest['total_demo_records']:,}")


if __name__ == "__main__":
    main()

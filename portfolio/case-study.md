# MergeMate: turning inconsistent spreadsheet exports into one auditable workbook

## Project snapshot

| Item | Detail |
| --- | --- |
| Project type | Solo portfolio project |
| Problem | Consolidating recurring CSV/XLSX exports with inconsistent headers, missing columns, and duplicates |
| Users | Analysts, operations teams, small businesses, and anyone maintaining a recurring master spreadsheet |
| Stack | Python 3.11+, pandas, openpyxl, Streamlit, pytest, Ruff |
| Interfaces | Streamlit app and argparse CLI |
| Dataset | UCI Steel Industry Energy Consumption (CC BY 4.0) |
| Verification | 68 tests passing; Ruff clean; CLI and app run end to end |
| Output | Formatted Excel workbook, consolidated CSV, JSON report, CSV report |

## The problem

Recurring spreadsheet consolidation usually starts as a copy-paste job:

1. Open every monthly export.
2. Find the column that means "usage" even though it is named `Usage kWh`,
   `Usage_kWh`, or `usage_kwh`.
3. Notice that one file is missing a column.
4. Decide whether to fill blanks, drop the column, or exclude the file.
5. Find duplicate rows.
6. Paste everything into a master sheet.
7. Try to remember what was changed when someone asks three weeks later.

The copy-paste version is slow, but the bigger problem is that the decisions are
invisible. A merged file does not explain why a column is blank, which file was
skipped, or which duplicate survived.

MergeMate treats those decisions as first-class output.

## What the tool does

MergeMate reads multiple `.csv` and `.xlsx` files and builds an explicit mapping
plan before writing anything. It then applies the selected missing-column and
duplicate policies, performs optional type normalization, and exports:

- a formatted Excel workbook with four sheets;
- a UTF-8 consolidated CSV;
- a structured JSON report;
- a flattened CSV report.

The same engine powers both the Streamlit interface and the CLI. The app is for
review and exploration; the CLI is for repeatable runs.

## Demo walkthrough

The bundled demo uses four quarterly files derived from the UCI steel-industry
energy dataset: two CSV and two XLSX. The headers intentionally differ, Q4 omits
`CO2 (tCO2)`, and Q4 contains one exact duplicate.

1. **Load the files.** The app shows file types, worksheet names, row counts, and
   a preview of each input.
2. **Review the mapping.** MergeMate normalizes 32 distinct source headers into a
   common schema. The mapping matrix shows the source header for every output
   column in every file. Q4's missing `co2_tco2` is highlighted; similar-but-
   different names are suggestions, not silent merges.
3. **Choose policies.** The demo uses "fill missing columns with blanks" and
   "remove exact duplicate rows." The app also supports excluding incomplete
   columns or rejecting incompatible files, plus key-based deduplication.
4. **Build a preview.** The preview shows 35,041 input rows, 35,040 output rows,
   one removed duplicate, and the consolidated rows before export.
5. **Export.** The app writes the workbook, CSV, and both reports, then offers
   downloads and a per-file processing summary.
6. **Repeat from the CLI.** The same decisions can be encoded in a command:
   `mergemate merge data/sample_inputs --output output --duplicates exact
   --parse-date date --report-format both`.

## Engineering decisions

### One engine, two interfaces

The most important architectural choice was to keep all processing rules in
`mergemate/consolidation.py` and the supporting modules. The Streamlit app calls
those modules directly; it does not have a separate merge implementation. This
avoids the classic problem where the UI and the batch job disagree.

### Explicit mapping over optimistic fuzzy matching

Header normalization handles predictable variation: case, spaces, punctuation,
and underscores. But genuinely different names are not merged automatically.
Close matches are shown as suggestions in the report, and the user can map them
explicitly. This is deliberately conservative: a wrong silent merge is worse
than a visible unmapped column.

### Missing-column policies are explicit

The tool supports three policies because there is no single correct answer:

- **blank** preserves the union of columns and fills gaps;
- **exclude** keeps only columns common to every file;
- **reject** stops when schemas are incompatible.

The report records which policy was applied and which columns were filled or
excluded.

### Detected facts are separate from applied changes

The JSON report has separate `detected` and `applied` sections. Exact duplicates
can be counted even when the policy is `keep-all`. Missing columns can be listed
even when they are filled with blanks. This makes the report useful for auditing,
not just for summarizing the final row count.

### Read-only inputs and deterministic demos

Input files are only read. A test hashes the inputs before and after a full
export to verify they are unchanged. The demo generator selects the same records
and headers for the fixed source file, and the test suite checks deterministic
processing.

### Bounded, local processing

MergeMate is intentionally not a data platform. It processes files in memory and
enforces modest limits: 25 MB per file, 50,000 rows per file, 200,000 rows per
run, 200 columns, and 20 files. There is no database, cloud service, API, queue,
or orchestration layer.

## Verification

The repository includes 68 tests:

| Area | Tests |
| --- | ---: |
| File readers | 18 |
| Column mapping | 13 |
| Consolidation | 16 |
| Export and reporting | 10 |
| CLI | 11 |

The suite covers mixed CSV/XLSX reading, delimiter/decimal detection, worksheet
selection, malformed and empty files, limits, header normalization, explicit
mapping, ignored columns, missing-column strategies, duplicate modes, type
conversions, workbook formatting, report accuracy, CLI exit codes, input
immutability, and determinism.

Commands:

```bash
pytest -q        # 68 passed
ruff check .     # All checks passed
```

The demo run was also verified end to end:

```text
Input:   4 files, 35,041 rows
Output:  35,040 rows, 12 columns
Removed: 1 exact duplicate
Sheets:  Consolidated Data, Processing Summary, Column Mapping, Validation Issues
```

## Tradeoffs and limitations

- **No source-format preservation.** The output is a fresh workbook. Macros,
  formulas, charts, pivot tables, merged cells, and specialized formatting from
  the inputs are not preserved. This is documented in the app and README.
- **One worksheet per input file.** Multi-sheet workbooks can be handled with an
  explicit worksheet selection, but MergeMate does not stack multiple sheets from
  the same workbook in one run.
- **No fuzzy auto-merge.** Suggestions are advisory. A human must confirm
  genuinely different header names.
- **In-memory limits.** The tool is designed for everyday spreadsheet volumes,
  not millions of rows.
- **Exact duplicates ignore `Source_File`.** Two identical records from different
  files are treated as duplicates under the exact policy. That is the intended
  behavior for consolidation, but it is a policy choice, not a universal truth.

## What I would build next

- Saved run profiles so a recurring monthly job can be replayed with one command.
- An optional `.xls`/`.xlsm` reader with a clear warning about macro handling.
- A dry-run diff that shows exactly which rows and columns would change before
  export.
- More UI-level tests around session-state transitions and download behavior.
- Optional chunked processing for larger files, without changing the core engine.

## Links

- Root README: [`../README.md`](../README.md)
- Dataset attribution and checksums: [`../data/README.md`](../data/README.md)
- Screenshots and capture notes: [`../docs/screenshots/README.md`](../docs/screenshots/README.md)
- Mapping example: [`../examples/mapping.json`](../examples/mapping.json)

## Dataset credit

The demo uses the **Steel Industry Energy Consumption** dataset:

> V E, S., Shin, C., & Cho, Y. (2021). Steel Industry Energy Consumption
> [Dataset]. UCI Machine Learning Repository.
> [https://doi.org/10.24432/C52G8C](https://doi.org/10.24432/C52G8C)

Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The demo files are derived by splitting the source by quarter, changing header
labels, standardizing date strings, omitting the Q4 CO2 column, and adding one
duplicate Q4 record. See [`../data/README.md`](../data/README.md) for details.

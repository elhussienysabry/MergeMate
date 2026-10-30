# Five-minute MergeMate demo script

Use this for a live call, a recorded Loom, or a portfolio walkthrough. The timings
are approximate. Have the app already running and the sample files loaded before
you start recording.

## Before you start

```bash
cd mergemate
source .venv/bin/activate
streamlit run app.py
```

Open the local URL. Keep a terminal window ready for the CLI segment.

## 0:00–0:30 — Frame the problem

**Say:**

> Recurring spreadsheet exports rarely have the same shape. One file says
> `Usage kWh`, another says `Usage_kWh`, one is missing a column, and there may
> be duplicate rows. Copy-pasting them into a master sheet is slow and the
> decisions are invisible afterward.
>
> MergeMate makes those decisions reviewable before it writes the output.

**Show:** screenshot `01-home.png` or the live landing page. Point out the four
steps: add files, review mapping, configure, preview and export.

## 0:30–1:15 — Load real files

**Do:** Click **Load bundled sample files**.

**Say:**

> These are four quarterly files derived from a real public dataset from the UCI
> Machine Learning Repository: two CSV, two XLSX, 35,041 rows in total. The
> headers intentionally vary. Q4 is missing the CO2 column, and it contains one
> duplicate row.

**Show:** the input summary and the preview tabs. Point out the CSV delimiter,
encoding, and decimal detection, and the worksheet names for the XLSX files.

## 1:15–2:15 — Review the mapping

**Do:** Scroll to **2 · Review column mapping**.

**Say:**

> MergeMate normalized 32 distinct source headers into a common snake_case
> schema. This matrix shows the exact source header for every output column in
> every file.
>
> Q4 is missing `co2_tco2`. The app shows that clearly instead of silently
> inventing a column. Similar names are only suggestions; they are not merged
> without an explicit mapping.

**Show:** the mapping matrix, the missing-column warning, and the manual mapping
expander (do not change anything unless the audience asks).

## 2:15–2:50 — Choose the rules

**Do:** Scroll to **3 · Consolidation options**. Select **Remove exact duplicate
rows**.

**Say:**

> The missing-column policy is fill with blanks. The duplicate policy is exact:
> compare every output data column except `Source_File`, and keep the first
> occurrence. The other options are exclude the incomplete column or reject
> incompatible files, plus key-based deduplication.

**Show:** the duplicate radio, the source-column field, and the optional
normalization expander.

## 2:50–3:30 — Build the preview

**Do:** Click **Build preview**.

**Say:**

> The preview shows 35,041 input rows and 35,040 output rows. One exact duplicate
> was removed. Nothing has been written yet; this is still in memory.

**Show:** the four preview metrics, the consolidated table, and the rows-by-source
table. Point out that Q4 has 8,833 input rows and 8,832 output rows because its
duplicate was removed.

## 3:30–4:15 — Export the workbook

**Do:** Click **Run consolidation and export**.

**Say:**

> The export writes a formatted workbook, a consolidated CSV, and both report
> formats. The workbook has four sheets: Consolidated Data, Processing Summary,
> Column Mapping, and Validation Issues.
>
> The Processing Summary records what was detected and what was applied, so the
> run is auditable later.

**Show:** the success metrics, the four download buttons, and the processing
summary. Optionally open `07-workbook-summary.png` to show the rendered summary
sheet.

## 4:15–4:50 — Show the CLI

**Do:** Switch to the terminal and run:

```bash
python -m mergemate.cli merge data/sample_inputs --output output/screenshot-run \
  --duplicates exact --parse-date date --report-format both
```

**Say:**

> The CLI uses the same engine. The flags encode the same decisions we just made
> in the UI, so a reviewed run can become a repeatable monthly command. It
> prints the output paths and the duplicate count.

**Show:** the CLI output, especially the four output paths and the final row
count.

## 4:50–5:00 — Close with verification

**Say:**

> The repository has 68 automated tests covering the readers, mapping,
> consolidation, exports, reports, and CLI. Ruff is clean. Original inputs are
> verified unchanged by a hash-based test.
>
> The demo dataset is CC BY 4.0 with attribution in the repository. The code is
> MIT.

**Show:** `10-tests-lint.png` or run `pytest -q` and `ruff check .`.

## Optional questions to ask the audience

- Which of your recurring exports is the most painful to combine?
- When a column is missing, would you rather fill blanks, drop the column, or
  stop and fix the source?
- How do you currently decide which duplicate row is the "right" one?
- Does the next person need a workbook, a CSV, or both?

## Do not say

- "It uses AI" — it does not.
- "It preserves your macros/formulas" — it writes a fresh workbook and does not.
- "It handles any size" — it has documented local limits.
- "It saved a client X hours" — no such verified claim is part of this project.

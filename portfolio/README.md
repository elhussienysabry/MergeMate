# MergeMate portfolio package

This folder turns the working MergeMate repository into a presentable freelance
portfolio package. Every claim here is backed by the code, tests, or screenshots
in this repository.

## The one-paragraph pitch

MergeMate is a local-first CSV and Excel consolidation tool for people who
receive the same report in a different shape every month. It reads mixed CSV and
XLSX files, normalizes headers, shows an explicit column mapping, handles missing
columns and duplicates, and exports a formatted workbook with a processing
report. The Streamlit interface and the CLI share one processing engine, so a
reviewed interactive run can be repeated from the command line.

## What is in this folder

| File | Use it for |
| --- | --- |
| `case-study.md` | A detailed project write-up for a portfolio site, GitHub, or interview. |
| `upwork-proposal.md` | A reusable proposal and scope template for spreadsheet-automation work. |
| `demo-script.md` | A five-minute walkthrough for a call, Loom, or live demo. |
| `linkedin-post.md` | A short launch post draft. |
| `screenshots/README.md` | Where the real captures live and what each one proves. |

## Verified project facts

Use these numbers rather than inventing marketing metrics:

- **68 automated tests pass** (`pytest -q`).
- **Ruff reports no issues** (`ruff check .`).
- The demo consolidates **35,041 input rows** from four files into **35,040
  output rows** with the exact-duplicate policy.
- The demo removes **one** documented duplicate and fills **one** missing column
  (`co2_tco2` in Q4).
- The output has **12 columns**: 11 data columns plus `Source_File`.
- The workbook has **four sheets**: `Consolidated Data`, `Processing Summary`,
  `Column Mapping`, and `Validation Issues`.
- The dataset is real, public, and licensed **CC BY 4.0**; attribution is in
  `data/README.md`.
- There are **11 genuine screenshots** in `docs/screenshots/`.

## Suggested portfolio placement

1. Lead with screenshot `01-home.png`.
2. Follow with `03-column-mapping.png` and `05-preview.png` to show that the tool
   makes decisions visible, not just output.
3. Use `06-export.png` and `07-workbook-summary.png` to show the deliverable.
4. Use `09-cli-run.png` and `10-tests-lint.png` to show repeatability and
   engineering discipline.
5. Link to the repository and the case study.

## What this package deliberately does not claim

- No client revenue, hours saved, or conversion-rate claims.
- No "AI" or "machine learning" features.
- No enterprise security, cloud, or multi-user claims.
- No claim that the workbook preserves source macros, formulas, or charts.

Those omissions are intentional. The project is strongest when it is presented
as a focused, tested, local automation tool.

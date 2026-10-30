# Upwork proposal and scope template

This is a reusable template for spreadsheet-consolidation and reporting work.
Replace the bracketed placeholders with the client's actual context. Do not
promise features or turnaround times that have not been agreed.

## Gig title options

- Consolidate multiple Excel/CSV files into one clean workbook
- Automate a recurring Excel merge with Python
- Clean, merge, and validate messy spreadsheet exports
- Build a repeatable CSV/Excel consolidation workflow

## Short gig description

> I build small, reliable Python tools that turn a folder of inconsistent Excel
> and CSV exports into one clean workbook — with a reviewable column mapping,
> duplicate handling, missing-column rules, and a processing report. I can
> deliver a one-off cleaned workbook or a repeatable CLI/Streamlit workflow your
> team can run again next month.

## Proposal template

**Subject:** Consolidating your [monthly/weekly] [CSV/Excel] exports into one
reliable workbook

Hi [Client name],

You mentioned that you receive [number] files per [month/week], with headers
that do not always match and occasional missing columns or duplicates. I can
build a repeatable consolidation workflow for that.

Here is how I would approach it:

1. **Inspect the real exports.** I will look at a representative sample and
   document the header variations, missing columns, duplicate rules, and any
   date/number formats.
2. **Make the mapping explicit.** I will normalize the headers and show which
   source column maps to which output column. Different names will not be merged
   silently.
3. **Agree the business rules.** We will confirm what should happen when a column
   is missing (fill, exclude, or reject) and which rows count as duplicates.
4. **Build and verify.** I will implement the workflow in Python, test it on your
   files, and check that the original files are untouched.
5. **Deliver the output and the repeatable command.** You will receive the
   consolidated workbook, a short processing report, and a command or simple app
   you can run again.

A relevant demo is in my portfolio: MergeMate consolidates four mixed CSV/XLSX
files, handles a missing column and a duplicate, and produces a four-sheet Excel
workbook plus JSON/CSV reports. The same engine powers both the app and the CLI.
The repository includes 68 automated tests and a full walkthrough with real
screenshots.

To scope this accurately, could you share:

- 2–3 representative input files (or a sample with the same structure);
- the desired output columns and any required order;
- how you currently decide a row is a duplicate;
- what should happen when a column is missing from one file;
- whether you need a one-off cleanup or a repeatable monthly process.

If it helps, I can start with a small paid sample on one month of data. That
gives you a concrete output to review before committing to the full workflow.

Best,
[Your name]
[Portfolio link] · [Email]

## Discovery questions

### Inputs

- How many files arrive per run, and how large are they?
- Are they all CSV, all Excel, or mixed?
- Do any workbooks contain multiple worksheets?
- Which CSV delimiter, encoding, and decimal format are used?
- Are the headers stable, or do they change between exports?

### Output

- What are the required output columns and their order?
- Does the output need a source-file column?
- Should the result be one workbook, one CSV, or both?
- Are there required sheet names, formulas, formatting, or a template?
- Who reviews the output, and what do they check first?

### Rules

- What makes two rows duplicates?
- If duplicates exist, should the first or last record win?
- What should happen when a column is missing from some files?
- Should invalid dates or numbers be blanked, flagged, or rejected?
- Are there columns that should always be ignored?

### Operations

- Is this a one-off cleanup or a recurring job?
- If recurring, how often does it run, and who runs it?
- Does it need to run on Windows, macOS, or Linux?
- Are there privacy or data-retention requirements?
- What does "done" look like for the first delivery?

## Scope packages

Use these as a starting point, not a fixed price list. Adjust for file count,
schema complexity, and review cycles.

### Starter: one-off consolidation

- Up to [N] input files and [N] output columns.
- One agreed missing-column policy and one duplicate policy.
- Cleaned Excel workbook and CSV.
- Short processing summary.
- One revision round.

### Standard: repeatable workflow

- Everything in Starter.
- A Python CLI or a small Streamlit app for repeat runs.
- Configurable mapping and policies.
- JSON/CSV processing report.
- Basic automated tests for the agreed rules.
- Handover notes and a recorded walkthrough.

### Advanced: recurring reporting pipeline

- Everything in Standard.
- Multiple input layouts or worksheet selections.
- Validation rules for dates, numbers, and required fields.
- A documented runbook and error handling for bad files.
- Optional scheduling guidance (the client's environment, not a hosted service).
- A support window for questions after delivery.

## What the client needs to provide

- Representative input files with sensitive values removed or approved for use.
- The desired output schema and column order.
- The duplicate and missing-column rules.
- A named reviewer and a reasonable review window.
- Confirmation of the environment where the workflow will run.

## Delivery process

1. **Kickoff and sample review** — confirm scope, rules, and acceptance criteria.
2. **Mapping and dry run** — show the proposed mapping and a preview before the
   final export.
3. **Build** — implement the workflow and automated checks.
4. **Review** — deliver a sample output and address one consolidated round of
   feedback.
5. **Handover** — provide the files, run instructions, and a short walkthrough.

## Assumptions and exclusions

- The client owns or has permission to use the input data.
- Source workbooks are not password-protected or corrupted.
- The output is a fresh workbook; source macros, charts, formulas, and
  specialized formatting are not preserved unless explicitly scoped.
- MergeMate's demo limits (25 MB per file, 50,000 rows per file, 200,000 rows per
  run) are a reference point, not a promise for every engagement.
- Cloud hosting, multi-user authentication, database design, and ongoing
  operations are separate scopes.

## Proof to link

- Root README: [`../README.md`](../README.md)
- Case study: [`case-study.md`](case-study.md)
- Screenshots: [`../docs/screenshots/`](../docs/screenshots/)
- Tests and lint capture: [`../docs/screenshots/10-tests-lint.png`](../docs/screenshots/10-tests-lint.png)
- Dataset attribution: [`../data/README.md`](../data/README.md)

## Closing line

> If you send 2–3 representative files and the output columns you need, I can
> tell you exactly what is feasible, what rules need a decision, and what the
> first deliverable would look like.

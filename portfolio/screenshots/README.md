# Portfolio screenshots

The canonical screenshot set lives in [`../../docs/screenshots/`](../../docs/screenshots/).
Those images are the real captures; this folder intentionally does not duplicate
them.

## Recommended order for a portfolio page

1. `01-home.png` — what the tool is.
2. `03-column-mapping.png` — the reviewable mapping, missing-column warning, and
   per-file schema.
3. `05-preview.png` — the before/after row counts and the consolidated preview.
4. `06-export.png` — downloads and the per-file processing summary.
5. `07-workbook-summary.png` — the actual workbook summary sheet.
6. `09-cli-run.png` — the same workflow as a repeatable command.
7. `10-tests-lint.png` — 68 tests passing and Ruff clean.

`02-input-summary.png` and `04-options.png` are useful supporting shots.
`08-cli-help.png` is useful when the audience cares about command-line
discoverability. `11-source-data-workbook.png` shows the generated data sheet
opened in LibreOffice Calc.

## What each image proves

| Image | Proof point |
| --- | --- |
| `01-home.png` | The product framing and the four-step workflow are clear. |
| `02-input-summary.png` | Mixed CSV/XLSX inputs, worksheet selection, and per-file row counts work. |
| `03-column-mapping.png` | Header normalization, explicit mapping, and missing-column detection are visible. |
| `04-options.png` | Missing-column, duplicate, source-column, and normalization controls exist. |
| `05-preview.png` | The app previews the actual result before writing files. |
| `06-export.png` | The export produces four downloadable artifacts and a source summary. |
| `07-workbook-summary.png` | The workbook contains a real, formatted processing summary. |
| `08-cli-help.png` | The CLI is a real argparse interface with documented options. |
| `09-cli-run.png` | The CLI processes 35,041 rows and reports output paths and duplicate removal. |
| `10-tests-lint.png` | The test suite and linter pass in the repository environment. |
| `11-source-data-workbook.png` | The generated workbook data sheet opens in LibreOffice Calc with all four tabs. |

See [`../../docs/screenshots/README.md`](../../docs/screenshots/README.md) for
capture methods and the exact demo settings.

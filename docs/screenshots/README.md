# Screenshots

These are captures of the running MergeMate app, the generated workbook, and
real terminal sessions. They are not mockups. The app captures use the bundled
steel-industry demo files, the **fill missing columns with blanks** policy, and
**remove exact duplicate rows**. That produces 35,041 input rows, 35,040 output
rows, and one removed duplicate.

| # | File | What it shows |
| --- | --- | --- |
| 01 | `01-home.png` | Landing page: product framing, four-step workflow, upload/sample controls, CSV parsing options, limits. |
| 02 | `02-input-summary.png` | Four bundled files loaded: two CSV, two XLSX, worksheet names, row/column counts, and a six-row input preview. |
| 03 | `03-column-mapping.png` | Mapping metrics, proposed output schema, the per-file mapping matrix, the missing `co2_tco2` warning, and file-specific columns. |
| 04 | `04-options.png` | Missing-column policy, source-file column, duplicate policy (exact selected), and the optional normalization controls. |
| 05 | `05-preview.png` | Built preview: 35,041 input rows, 35,040 output rows, 1 duplicate removed, and the consolidated data preview. |
| 06 | `06-export.png` | Completed export: success message, five run metrics, four download buttons, and the per-file processing summary. |
| 07 | `07-workbook-summary.png` | The actual `Processing Summary` worksheet from the exported workbook, rendered through LibreOffice. |
| 08 | `08-cli-help.png` | `python -m mergemate.cli --help` in a real Konsole window. |
| 09 | `09-cli-run.png` | A real CLI consolidation run: 35,040 rows, 12 columns, four output paths, one duplicate removed. |
| 10 | `10-tests-lint.png` | Real `pytest -q` and `ruff check .` output: 68 tests passed and lint clean. |
| 11 | `11-source-data-workbook.png` | The generated `Consolidated Data` sheet from a separate run on the original source CSV, opened in LibreOffice Calc; all four workbook tabs are visible. |

## Capture details

- **01–06:** Playwright with the system Google Chrome, viewport 1600×1000,
  device scale factor 1.25. The Streamlit toolbar was hidden for a cleaner
  capture; the app content, sidebar, tables, and buttons are unchanged.
- **07:** The workbook shown is the real export from the UI run. To keep the
  PDF render short, a temporary copy of the workbook was made with the 35,040-row
  `Consolidated Data` sheet removed. The `Processing Summary` sheet was not
  otherwise edited. It was converted to PDF with LibreOffice headless and
  rasterized with `pdftoppm`. The shipped workbook still contains all four
  sheets.
- **08–10:** Real Konsole windows captured with Spectacle's active-window mode.
  The terminal prompt lines were printed before running the real commands; the
  command output is genuine. The terminal window was cropped at the bottom to
  remove unused space.
- **11:** A real workbook from a separate verification run on
  `data/source/Steel_industry_data.csv`, opened in LibreOffice Calc. It is not
  one of the four-file demo captures; it shows the generated data sheet and the
  four workbook tabs.

## Recreating the app captures

Start the app from the repository root:

```bash
streamlit run app.py
```

Then load **Load bundled sample files**, select **Remove exact duplicate rows**,
build the preview, and export. The exported workbook and reports are written to
`output/`.

The exact demo command shown in screenshot 09 is:

```bash
python -m mergemate.cli merge data/sample_inputs --output output/screenshot-run \
  --duplicates exact --parse-date date --report-format both
```

See the root [`README.md`](../../README.md) for setup and the full command
reference.

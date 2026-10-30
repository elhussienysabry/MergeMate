# LinkedIn launch post draft

I built MergeMate, a small tool for a problem that shows up in almost every
spreadsheet-heavy team: the same report arrives every month in a slightly
different shape.

One file uses `Usage kWh`, another uses `Usage_kWh`, a third is missing a column,
and there are duplicate rows somewhere in the stack. The usual solution is a
manual copy-paste into a master sheet — slow, hard to review, and impossible to
audit three weeks later.

MergeMate is a local-first Streamlit app and CLI that:

- reads multiple CSV and XLSX files in one run;
- normalizes headers and shows an explicit column mapping;
- handles missing columns with fill, exclude, or reject policies;
- removes exact duplicates or duplicates by selected key columns;
- optionally trims, parses dates, and converts numbers, reporting invalid values;
- exports a formatted four-sheet Excel workbook plus CSV and JSON/CSV reports.

The app and CLI share the same processing engine, so a reviewed interactive run
can become a repeatable command. The repo includes 68 automated tests, Ruff
clean, and real screenshots of the app, workbook, CLI, and test run.

The demo uses the UCI Steel Industry Energy Consumption dataset (CC BY 4.0),
split into four quarterly files with documented header variations, a missing
column, and one duplicate.

Repo/demo: [link]

#Python #DataEngineering #Excel #Automation #Streamlit #PortfolioProject

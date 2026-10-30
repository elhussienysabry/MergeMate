# Demo data and attribution

MergeMate's bundled demo uses a real public dataset. No synthetic records are
used. The source file is stored unchanged in `data/source/`, and four
demonstration inputs are derived from it in `data/sample_inputs/`.

## Source dataset

| Item | Value |
| --- | --- |
| Title | Steel Industry Energy Consumption |
| Creators | Sathishkumar V E, Changsun Shin, Yongyun Cho |
| Year | 2021 |
| Publisher | UCI Machine Learning Repository |
| DOI | [10.24432/C52G8C](https://doi.org/10.24432/C52G8C) |
| Dataset page | <https://archive.ics.uci.edu/dataset/851/steel+industry+energy+consumption> |
| License | [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) |
| Downloaded | 2026-10-28 |
| Source file | `data/source/Steel_industry_data.csv` |
| Source SHA-256 | `9b1cee6f9cb9cd9df2b95814ca90a9a2ff15b7f5f1fba0fae3c643e82072eacc` |
| Source records | 35,040 |
| Source columns | 11 |

The source CSV contains 15-minute energy measurements from a small-scale steel
industry in South Korea during 2018. It has a UTF-8 byte-order mark and uses
`DD/MM/YYYY HH:MM` timestamps.

### Required citation

> V E, S., Shin, C., & Cho, Y. (2021). Steel Industry Energy Consumption
> [Dataset]. UCI Machine Learning Repository.
> https://doi.org/10.24432/C52G8C

## Derived demonstration files

`scripts/prepare_sample_data.py` splits the source into 2018 calendar quarters.
It changes **header labels** to demonstrate normalization, writes dates in one
consistent string format across CSV and XLSX, omits one optional column from Q4,
and adds one exact duplicate record to Q4. Data values are otherwise unchanged.

| File | Quarter | Format | Rows | Cols | Header style | CSV parsing | Missing column | Duplicate rows | SHA-256 |
| --- | --- | --- | ---: | ---: | --- | --- | --- | ---: | --- |
| `steel_energy_2018_q1.csv` | 2018 Q1 | CSV | 8,640 | 11 | Spaced, readable labels | `;` delimiter, `,` decimal | — | 0 | `60f76ed5f4db4b066c228740d53f994f0a7a5fbb3220b0ba7063665c710c7643` |
| `steel_energy_2018_q2.xlsx` | 2018 Q2 | XLSX | 8,736 | 11 | Original-style mixed labels | n/a | — | 0 | `3af1e3d544f5eceb65e7c11b133d1e64ecb3a1b2f7b062cbe3f109c6d5aecc84` |
| `steel_energy_2018_q3.csv` | 2018 Q3 | CSV | 8,832 | 11 | `snake_case` labels | `;` delimiter, `,` decimal | — | 0 | `a408701ce69c3c907a64ad9a2a312302b2e61b4874ffff0ddaf1384c5920c116` |
| `steel_energy_2018_q4.xlsx` | 2018 Q4 | XLSX | 8,833 | 10 | Spaced labels, one column omitted | n/a | `CO2 (tCO2)` | 1 | `056ea3cd87abc5b1523328edb611f3220d70fc9b35626ae6b65922977b27866c` |

Total demonstration records: **35,041** (35,040 unique records plus the one
documented duplicate). With the `exact` duplicate policy, the default demo
produces **35,040** output rows.

The machine-readable copy of this metadata, including per-file checksums, is in
`data/sample_inputs/manifest.json`. The checksums identify the copies shipped in
this repository. Re-running the generator with a different pandas or openpyxl
version can change serialization details and XLSX ZIP metadata, so regenerated
files may not be byte-identical even when they contain the same records, row
order, and headers.

### Header variations

The four files intentionally use different labels for the same fields. For
example:

| Q1 | Q2 | Q3 | Q4 |
| --- | --- | --- | --- |
| `Usage kWh` | `Usage_kWh` | `usage_kwh` | `Usage (kWh)` |
| `Week Status` | `Week_Status` | `week_status` | `Week Status` |
| `Day of Week` | `Day_of_week` | `day_of_week` | `Day of Week` |
| `CO2 (tCO2)` | `CO2(tCO2)` | `co2_tco2` | *(column absent)* |

MergeMate normalizes all of these to a common snake_case schema. Different names
are never merged silently: exact normalized matches are automatic, while genuinely
different names require an explicit mapping.

### Worksheet names

Both XLSX files contain a single worksheet named `Energy Data`. The CLI can
select a worksheet explicitly with `--sheet "file.xlsx=Sheet Name"`; the app shows
a selector when a workbook has more than one worksheet.

## Regenerating the demo inputs

From the repository root, with the project dependencies installed:

```bash
python scripts/prepare_sample_data.py
```

For the fixed source file, the script deterministically selects the same
records, row order, and headers on each run. It rewrites the four sample inputs
and `manifest.json`, then prints the total demo record count. The manifest and
checksums can be checked directly; the test suite focuses on the processing
engine rather than regenerating the demo data.

## License and attribution notes

- The **dataset** is licensed under **CC BY 4.0**, not the MIT license that
  covers MergeMate's source code. Reuse of the dataset or the derived sample
  files must retain appropriate credit to the creators, link to the license, and
  indicate that changes were made.
- The changes made for this demo are: splitting by calendar quarter, changing
  header labels, standardizing the date string format, omitting the Q4 CO2
  column, and adding one duplicate Q4 record.
- The dataset is redistributed here for demonstration purposes with attribution.
  If you fork this project, keep this file and the citation with the data.

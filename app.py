"""Streamlit interface for MergeMate.

The UI deliberately delegates every processing decision to the same modules
used by the CLI: file_readers, column_mapping, consolidation, reporting, and
export. It never implements a second version of the consolidation rules.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st

from mergemate.column_mapping import build_mapping_plan
from mergemate.config import (
    APP_NAME,
    APP_VERSION,
    CSV_DECIMAL_OPTIONS,
    CSV_DELIMITER_OPTIONS,
    CSV_ENCODING_OPTIONS,
    DEFAULT_SOURCE_COLUMN,
    DUPLICATE_MODE_LABELS,
    MAX_FILE_SIZE_BYTES,
    MAX_FILES,
    MAX_ROWS_PER_FILE,
    MAX_TOTAL_ROWS,
    MISSING_STRATEGIES,
    MISSING_STRATEGY_LABELS,
    PREVIEW_ROWS,
    SAMPLE_INPUT_DIR,
)
from mergemate.consolidation import ConsolidationOptions, consolidate
from mergemate.exceptions import MergeMateError
from mergemate.export import export_all, make_output_base_name
from mergemate.file_readers import (
    LoadedFile,
    ReadOptions,
    check_total_rows,
    list_excel_sheets,
    load_input_files,
)
from mergemate.reporting import build_report
from mergemate.validation import ValidationIssue

st.set_page_config(
    page_title="MergeMate — Excel & CSV consolidation",
    page_icon="▦",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULTS = {
    "source_mode": None,
    "uploader_key": 0,
    "upload_dir": None,
    "upload_signature": None,
    "sheet_selections": {},
    "mapping_overrides": {},
    "preview": None,
    "preview_signature": None,
    "export_data": None,
    "export_signature": None,
    "last_signature": None,
    "delimiter_label": "auto",
    "encoding_label": "auto",
    "decimal_label": "auto",
    "skip_invalid": False,
    "missing_strategy": "blank",
    "duplicate_mode": "keep_all",
    "duplicate_keys": [],
    "duplicate_keep": "first",
    "source_column": DEFAULT_SOURCE_COLUMN,
    "trim_cols": [],
    "date_cols": [],
    "numeric_cols": [],
}


def display_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Render object columns as text so Arrow never sees mixed Python types."""
    display = df.copy()
    for column in display.columns:
        if display[column].dtype == object:
            display[column] = display[column].map(
                lambda value: "" if pd.isna(value) else str(value)
            )
    return display


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1450px;}
        .mm-hero {
            background: linear-gradient(120deg, #0f172a 0%, #134e4a 62%, #0f766e 100%);
            border-radius: 20px;
            padding: 28px 34px 26px 34px;
            color: white;
            margin-bottom: 20px;
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.16);
        }
        .mm-kicker {
            font-size: 0.72rem;
            letter-spacing: 0.16em;
            font-weight: 700;
            color: #99f6e4;
            margin-bottom: 6px;
        }
        .mm-hero h1 {font-size: 2.6rem; line-height: 1.05; margin: 0 0 8px 0; color: white;}
        .mm-hero p {font-size: 1.03rem; max-width: 820px; color: #d1fae5; margin: 0 0 16px 0;}
        .mm-tags span {
            display: inline-block;
            border: 1px solid rgba(153, 246, 228, 0.35);
            background: rgba(15, 118, 110, 0.35);
            border-radius: 999px;
            padding: 4px 11px;
            margin: 0 7px 6px 0;
            font-size: 0.78rem;
            color: #ccfbf1;
        }
        .mm-step {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 14px 16px;
            min-height: 96px;
        }
        .mm-step .num {
            display: inline-block;
            width: 23px; height: 23px; line-height: 23px;
            text-align: center; border-radius: 50%;
            background: #0f766e; color: white; font-size: 0.76rem;
            font-weight: 700; margin-right: 7px;
        }
        .mm-step b {color: #0f172a; font-size: 0.94rem;}
        .mm-step span {display: block; color: #64748b; font-size: 0.8rem; margin-top: 6px;}
        div[data-testid="stMetric"] {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 10px 14px;
        }
        div[data-testid="stMetricLabel"] p {font-size: 0.78rem; color: #64748b;}
        .mm-note {
            background: #f0fdfa;
            border-left: 4px solid #0f766e;
            border-radius: 8px;
            padding: 10px 14px;
            color: #134e4a;
            font-size: 0.88rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value.copy() if isinstance(value, (dict, list)) else value


def clear_processing_state() -> None:
    st.session_state.preview = None
    st.session_state.preview_signature = None
    st.session_state.export_data = None
    st.session_state.export_signature = None


def cleanup_upload_dir() -> None:
    upload_dir = st.session_state.get("upload_dir")
    if upload_dir:
        shutil.rmtree(upload_dir, ignore_errors=True)
    st.session_state.upload_dir = None
    st.session_state.upload_signature = None


def reset_app() -> None:
    cleanup_upload_dir()
    for key in list(st.session_state.keys()):
        if key.startswith(("sheet_", "map_", "mapping_form_")):
            del st.session_state[key]
    for key, value in DEFAULTS.items():
        st.session_state[key] = value.copy() if isinstance(value, (dict, list)) else value
    st.session_state.uploader_key += 1
    st.rerun()


def render_sidebar() -> ReadOptions:
    with st.sidebar:
        st.markdown(f"## {APP_NAME}")
        st.caption("Consolidate spreadsheets without copy-paste.")
        st.markdown("#### Quick start")
        st.markdown(
            "1. Add CSV or Excel files.\n"
            "2. Review the proposed column mapping.\n"
            "3. Choose duplicate and missing-column options.\n"
            "4. Build a preview, then export."
        )
        st.divider()
        with st.expander("CSV parsing options", expanded=True):
            st.selectbox(
                "Delimiter",
                options=list(CSV_DELIMITER_OPTIONS),
                key="delimiter_label",
                help="Auto-detect is recommended. Use semicolon for many European exports.",
            )
            st.selectbox(
                "Text encoding",
                options=list(CSV_ENCODING_OPTIONS),
                key="encoding_label",
                help="Auto tries UTF-8 first, then common Western encodings.",
            )
            st.selectbox(
                "Decimal separator",
                options=list(CSV_DECIMAL_OPTIONS),
                key="decimal_label",
                help="Auto handles comma decimals in semicolon-delimited files.",
            )
        st.caption(
            f"Limits: {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB per file, "
            f"{MAX_ROWS_PER_FILE:,} rows per file, {MAX_TOTAL_ROWS:,} rows per run, "
            f"{MAX_FILES} files."
        )
        st.divider()
        st.caption("Original input files are only read, never modified.")
        if st.button("Reset session", width="stretch"):
            reset_app()
        st.caption(f"{APP_NAME} v{APP_VERSION} · local-first portfolio project")

    read_options = ReadOptions(
        csv_delimiter=CSV_DELIMITER_OPTIONS[st.session_state.delimiter_label],
        csv_encoding=CSV_ENCODING_OPTIONS[st.session_state.encoding_label],
        csv_decimal=CSV_DECIMAL_OPTIONS[st.session_state.decimal_label],
    )
    return read_options


def render_hero() -> None:
    st.markdown(
        """
        <div class="mm-hero">
          <div class="mm-kicker">SPREADSHEET AUTOMATION</div>
          <h1>MergeMate</h1>
          <p>
            Turn a folder of monthly CSV and Excel exports into one organized
            workbook — with a reviewable column mapping, duplicate handling,
            validation notes, and a processing report.
          </p>
          <div class="mm-tags">
            <span>CSV + XLSX</span>
            <span>Column mapping</span>
            <span>Duplicate controls</span>
            <span>Excel report workbook</span>
            <span>Runs locally</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    columns = st.columns(4)
    steps = [
        ("1", "Add files", "Upload multiple CSV/XLSX files or use the bundled demo."),
        ("2", "Review mapping", "See normalized headers, missing columns, and overrides."),
        ("3", "Configure", "Choose missing-column, duplicate, and type options."),
        ("4", "Preview & export", "Inspect the merged data, then download the workbook."),
    ]
    for column, (number, title, description) in zip(columns, steps, strict=True):
        with column:
            st.markdown(
                f'<div class="mm-step"><span class="num">{number}</span>'
                f"<b>{title}</b><span>{description}</span></div>",
                unsafe_allow_html=True,
            )


def save_uploads(uploaded_files) -> list[Path]:
    signature = tuple((file.name, file.size) for file in uploaded_files)
    if signature == st.session_state.upload_signature:
        upload_dir = Path(st.session_state.upload_dir or "")
        if upload_dir.is_dir():
            return sorted(upload_dir.glob("*"))

    if not st.session_state.upload_dir:
        st.session_state.upload_dir = tempfile.mkdtemp(prefix="mergemate_uploads_")
    upload_dir = Path(st.session_state.upload_dir)
    for existing in upload_dir.iterdir():
        if existing.is_file():
            existing.unlink()

    paths: list[Path] = []
    used_names: set[str] = set()
    for index, uploaded in enumerate(uploaded_files, start=1):
        safe_name = Path(uploaded.name).name or f"upload_{index}.csv"
        if safe_name in used_names:
            stem, suffix = Path(safe_name).stem, Path(safe_name).suffix
            safe_name = f"{stem}_{index}{suffix}"
        used_names.add(safe_name)
        destination = upload_dir / safe_name
        destination.write_bytes(uploaded.getbuffer())
        paths.append(destination)

    st.session_state.upload_signature = signature
    return sorted(paths)


def render_file_step(
    read_options: ReadOptions,
) -> tuple[list[LoadedFile], list[ValidationIssue], list[Path], dict[str, str]] | None:
    st.markdown("### 1 · Add input files")
    st.caption(
        "Add one or more .csv or .xlsx files. You can mix both formats in one run. "
        "Nothing is written back to the originals."
    )

    with st.container(border=True):
        upload_column, sample_column = st.columns([1.6, 1])
        with upload_column:
            uploaded_files = st.file_uploader(
                "Upload CSV or Excel files",
                type=["csv", "xlsx"],
                accept_multiple_files=True,
                key=f"file_uploader_{st.session_state.uploader_key}",
                help="Maximum 25 MB per file. Multiple files and mixed formats are supported.",
            )
        with sample_column:
            st.markdown("**Just exploring?**")
            st.caption("Load the documented steel-industry energy sample inputs.")
            if st.button("Load bundled sample files", width="stretch"):
                if not SAMPLE_INPUT_DIR.is_dir():
                    st.error(
                        "The bundled sample folder is missing. "
                        "Expected data/sample_inputs in the repository."
                    )
                else:
                    st.session_state.source_mode = "sample"
                    st.session_state.uploader_key += 1
                    st.session_state.mapping_overrides = {}
                    clear_processing_state()
                    st.rerun()

        paths: list[Path] = []
        if uploaded_files:
            if st.session_state.source_mode != "upload":
                st.session_state.source_mode = "upload"
                st.session_state.mapping_overrides = {}
                clear_processing_state()
            paths = save_uploads(uploaded_files)
        elif st.session_state.source_mode == "sample":
            paths = sorted(
                path
                for path in SAMPLE_INPUT_DIR.glob("*")
                if path.suffix.lower() in {".csv", ".xlsx"}
            )

        if paths:
            if st.session_state.source_mode == "sample":
                st.caption(
                    f"Using {len(paths)} bundled sample file(s) from data/sample_inputs "
                    "(read-only)."
                )
            else:
                st.caption(f"Using {len(paths)} uploaded file(s).")
            if st.button("Clear selected files", width="content"):
                st.session_state.source_mode = None
                st.session_state.uploader_key += 1
                st.session_state.mapping_overrides = {}
                cleanup_upload_dir()
                clear_processing_state()
                st.rerun()

    if not paths:
        st.info(
            "Start by uploading at least one CSV or Excel file, or load the bundled "
            "sample files. Steps 2–4 unlock after files are readable."
        )
        st.markdown(
            '<div class="mm-note">The demo files are real 15-minute steel-industry '
            "energy records split into four documented quarterly files. Two are CSV, "
            "two are XLSX, and their headers intentionally use different naming "
            "conventions.</div>",
            unsafe_allow_html=True,
        )
        return None

    # Worksheet selection is part of the input step because it changes how a
    # workbook is read. The same selection is passed to the shared reader.
    sheet_overrides: dict[str, str] = {}
    xlsx_paths = [path for path in paths if path.suffix.lower() == ".xlsx"]
    if xlsx_paths:
        st.markdown("#### Worksheet selection")
        for path in xlsx_paths:
            try:
                sheets = list_excel_sheets(path, read_options)
            except MergeMateError as exc:
                st.error(f"{path.name}: {exc}")
                continue
            previous = st.session_state.sheet_selections.get(path.name)
            if len(sheets) == 1:
                selected = sheets[0]
                st.caption(f"{path.name} · worksheet: **{selected}**")
            else:
                selected = st.selectbox(
                    f"Worksheet for {path.name}",
                    options=sheets,
                    index=sheets.index(previous) if previous in sheets else 0,
                    key=f"sheet_select_{path.name}",
                )
            if previous != selected:
                st.session_state.sheet_selections[path.name] = selected
                clear_processing_state()
            sheet_overrides[path.name] = selected

    # Clear mapping overrides if the set of input files changes.
    file_signature = tuple((str(path), sheet_overrides.get(path.name)) for path in paths)
    if st.session_state.get("last_file_signature") != file_signature:
        st.session_state.last_file_signature = file_signature
        st.session_state.mapping_overrides = {}
        clear_processing_state()

    with st.spinner("Reading inputs..."):
        files, issues = load_input_files(
            paths,
            read_options,
            sheet_overrides=sheet_overrides,
            max_files=MAX_FILES,
        )
    total_issue = check_total_rows(files, MAX_TOTAL_ROWS)
    if total_issue:
        st.error(total_issue.message)

    failed_issues = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]

    if total_issue:
        return None

    if failed_issues:
        for issue in failed_issues:
            label = f"{issue.file}: " if issue.file else ""
            st.error(f"{label}{issue.message}")
        skip_invalid = st.checkbox(
            "Skip unreadable files and continue with the rest",
            key="skip_invalid",
            help="Useful when one export is corrupt. The skipped files are listed in the report.",
        )
        if not skip_invalid:
            st.info(
                "Fix the input files or enable the skip option to continue. "
                "No output is written until a preview is built."
            )
            return None
        st.warning(
            f"Continuing with {len(files)} readable file(s); "
            f"{len(failed_issues)} file(s) will be recorded as failed."
        )

    if not files:
        st.error("No readable input files remain. Adjust the files and try again.")
        return None

    summary = pd.DataFrame(
        [
            {
                "File": loaded.display_name,
                "Type": loaded.file_type,
                "Worksheet": loaded.sheet_name or "—",
                "Rows": loaded.row_count,
                "Columns": loaded.column_count,
                "Status": "Ready",
            }
            for loaded in files
        ]
    )
    st.markdown("#### Input summary")
    st.dataframe(summary, hide_index=True, width="stretch")
    st.caption(
        f"{len(files)} file(s) · {sum(file.row_count for file in files):,} input rows · "
        f"{len({column for file in files for column in file.columns}):,} distinct source headers"
    )

    if warnings:
        with st.expander(f"File notes ({len(warnings)})", expanded=False):
            for issue in warnings:
                label = f"{issue.file}: " if issue.file else ""
                st.warning(f"{label}{issue.message}")

    st.markdown("#### Preview inputs")
    tabs = st.tabs([loaded.display_name for loaded in files])
    for tab, loaded in zip(tabs, files, strict=True):
        with tab:
            details = []
            if loaded.sheet_name:
                details.append(f"worksheet: {loaded.sheet_name}")
            if loaded.csv_delimiter:
                delimiter = {"\t": "tab", ",": "comma", ";": "semicolon", "|": "pipe"}.get(
                    loaded.csv_delimiter, loaded.csv_delimiter
                )
                details.append(f"delimiter: {delimiter}")
            if loaded.csv_encoding:
                details.append(f"encoding: {loaded.csv_encoding}")
            if loaded.csv_decimal:
                details.append(f"decimal: {loaded.csv_decimal}")
            if details:
                st.caption(" · ".join(details))
            st.dataframe(
                display_frame(loaded.dataframe.head(6)),
                hide_index=True,
                width="stretch",
            )
            st.caption(
                f"{loaded.row_count:,} rows · {loaded.column_count} columns · "
                f"showing first {min(6, loaded.row_count)}"
            )

    return files, issues, paths, sheet_overrides


def render_mapping_step(
    files: list[LoadedFile],
) -> tuple[object | None, str]:
    st.markdown("### 2 · Review column mapping")
    st.caption(
        "Headers are trimmed and normalized to snake_case for the output. "
        "Exact normalized matches are mapped automatically; different names are "
        "never merged silently."
    )

    known_files = {file.display_name for file in files}
    allowed_columns = {
        file.display_name: set(file.columns) for file in files
    }
    cleaned_overrides: dict[str, dict[str, str | None]] = {}
    for file_name, mapping in st.session_state.mapping_overrides.items():
        if file_name not in known_files:
            continue
        cleaned = {
            source: target
            for source, target in mapping.items()
            if source in allowed_columns[file_name]
        }
        if cleaned:
            cleaned_overrides[file_name] = cleaned
    st.session_state.mapping_overrides = cleaned_overrides

    try:
        plan = build_mapping_plan(files, overrides=cleaned_overrides)
    except MergeMateError as exc:
        st.error(f"Column mapping error: {exc}")
        return None, ""

    metrics = st.columns(4)
    metrics[0].metric("Output columns", len(plan.canonical_columns))
    metrics[1].metric("Common to every file", len(plan.common_columns))
    metrics[2].metric("Header differences", len(plan.header_differences()))
    metrics[3].metric("Files", len(files))

    matrix_rows = []
    for column in plan.canonical_columns:
        row = {"Output column": column}
        for loaded in files:
            mapping = plan.file_mappings[loaded.display_name]
            source = mapping.source_for_output(column)
            row[loaded.display_name] = source if source else "— missing —"
        matrix_rows.append(row)
    st.markdown("#### Proposed mapping")
    st.dataframe(
        pd.DataFrame(matrix_rows),
        hide_index=True,
        width="stretch",
    )

    differences = plan.header_differences()
    if differences:
        with st.expander(f"Detected header differences ({len(differences)})", expanded=False):
            st.dataframe(
                pd.DataFrame(differences),
                hide_index=True,
                width="stretch",
            )

    if plan.missing_columns_by_file:
        lines = [
            f"**{file_name}**: {', '.join(columns)}"
            for file_name, columns in plan.missing_columns_by_file.items()
        ]
        st.warning("Missing columns detected — " + " · ".join(lines))
    if plan.file_specific_columns_by_file:
        lines = [
            f"**{file_name}**: {', '.join(columns)}"
            for file_name, columns in plan.file_specific_columns_by_file.items()
        ]
        st.info("Columns present in only some files — " + " · ".join(lines))
    if plan.ignored_columns_by_file:
        st.caption(
            "Ignored source columns: "
            + "; ".join(
                f"{file_name}: {', '.join(columns)}"
                for file_name, columns in plan.ignored_columns_by_file.items()
            )
        )

    with st.expander("Map columns manually or exclude a column", expanded=False):
        st.caption(
            "Use these controls when two files use genuinely different header names. "
            "Mapping is explicit; choosing (ignore) removes that source column from the output."
        )
        schema_key = hashlib.sha1(
            "|".join(plan.canonical_columns).encode("utf-8")
        ).hexdigest()[:8]
        tabs = st.tabs([loaded.display_name for loaded in files])
        for index, (tab, loaded) in enumerate(zip(tabs, files, strict=True)):
            with tab:
                mapping = plan.file_mappings[loaded.display_name]
                with st.form(f"mapping_form_{index}"):
                    choices: dict[str, str] = {}
                    for source_index, source in enumerate(loaded.columns):
                        current = mapping.source_to_output.get(source, "")
                        options = ["(ignore)"] + plan.canonical_columns
                        default_index = options.index(current) if current in options else 0
                        choices[source] = st.selectbox(
                            source,
                            options=options,
                            index=default_index,
                            key=f"map_{index}_{source_index}_{schema_key}",
                        )
                    submitted = st.form_submit_button("Apply mapping for this file")
                    if submitted:
                        st.session_state.mapping_overrides[loaded.display_name] = {
                            source: (None if choice == "(ignore)" else choice)
                            for source, choice in choices.items()
                        }
                        clear_processing_state()
                        st.rerun()
        if st.button("Reset all mappings to automatic", width="content"):
            st.session_state.mapping_overrides = {}
            clear_processing_state()
            st.rerun()

    st.markdown("#### Missing-column policy")
    st.radio(
        "When a column is missing from some files",
        options=list(MISSING_STRATEGIES),
        format_func=lambda value: MISSING_STRATEGY_LABELS[value],
        horizontal=True,
        key="missing_strategy",
    )
    strategy = st.session_state.missing_strategy
    if strategy == "blank":
        st.caption(
            "The output keeps the union of columns. Rows from files without a column "
            "receive a blank value there."
        )
    elif strategy == "exclude":
        st.caption(
            "Only columns found in every readable file are exported. File-specific "
            "columns are listed in the report as excluded."
        )
    else:
        st.caption(
            "Processing is blocked if any file is missing a column. This is the "
            "strictest compatibility check."
        )
        if plan.missing_columns_by_file:
            st.warning(
                "The current files are incompatible under this policy. Choose another "
                "policy or remove the incompatible file."
            )

    return plan, strategy


def _signature(
    paths: list[Path],
    sheet_overrides: dict[str, str],
    overrides: dict[str, dict[str, str | None]],
    options: ConsolidationOptions,
    plan,
) -> str:
    payload = {
        "files": [
            {
                "name": path.name,
                "size": path.stat().st_size,
                "mtime_ns": path.stat().st_mtime_ns,
                "sheet": sheet_overrides.get(path.name),
            }
            for path in paths
        ],
        "mapping": overrides,
        "options": asdict(options),
        "columns": plan.canonical_columns,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def render_options_step(
    plan,
    strategy: str,
) -> ConsolidationOptions:
    st.markdown("### 3 · Consolidation options")
    for key in ("duplicate_keys", "trim_cols", "date_cols", "numeric_cols"):
        current = st.session_state.get(key, [])
        st.session_state[key] = [
            column for column in current if column in plan.canonical_columns
        ]
    source_column = st.text_input(
        "Source-file column name",
        key="source_column",
        help="Every output row records the file it came from.",
    )
    if not source_column.strip():
        st.error("The source-file column name cannot be blank.")
    elif source_column in plan.canonical_columns:
        st.error(
            f"'{source_column}' is already an output column. Choose another source "
            "column name."
        )

    st.markdown("#### Duplicate handling")
    st.radio(
        "Duplicate policy",
        options=["keep_all", "exact", "keys"],
        format_func=lambda value: DUPLICATE_MODE_LABELS[value],
        key="duplicate_mode",
    )
    duplicate_mode = st.session_state.duplicate_mode
    if duplicate_mode == "keep_all":
        st.caption("No records are removed. Exact duplicates are still counted in the report.")
    elif duplicate_mode == "exact":
        st.caption(
            "Exact duplicates compare every output data column except the source-file "
            "column. The first occurrence is kept."
        )
    else:
        key_columns = st.multiselect(
            "Key columns for duplicate detection",
            options=plan.canonical_columns,
            key="duplicate_keys",
            help="Rows with the same values in all selected key columns are duplicates.",
        )
        st.radio(
            "Which duplicate to keep",
            options=["first", "last"],
            horizontal=True,
            key="duplicate_keep",
        )
        if not key_columns:
            st.warning("Select at least one key column, or choose a different policy.")

    with st.expander("Optional data-type normalization", expanded=False):
        st.caption(
            "These operations are opt-in. Invalid dates or numbers become blank and "
            "are reported; rows are never deleted automatically."
        )
        st.multiselect(
            "Trim whitespace in text columns",
            options=plan.canonical_columns,
            key="trim_cols",
        )
        st.multiselect(
            "Parse as dates",
            options=plan.canonical_columns,
            key="date_cols",
        )
        st.multiselect(
            "Convert to numeric",
            options=plan.canonical_columns,
            key="numeric_cols",
        )

    return ConsolidationOptions(
        missing_column_strategy=strategy,
        duplicate_mode=st.session_state.duplicate_mode,
        duplicate_key_columns=tuple(st.session_state.duplicate_keys),
        duplicate_keep=st.session_state.duplicate_keep,
        source_column=source_column.strip(),
        trim_columns=tuple(st.session_state.trim_cols),
        date_columns=tuple(st.session_state.date_cols),
        numeric_columns=tuple(st.session_state.numeric_cols),
    )


def render_preview_and_export(
    files: list[LoadedFile],
    plan,
    options: ConsolidationOptions,
    issues: list[ValidationIssue],
    current_signature: str,
) -> None:
    st.markdown("### 4 · Preview and run")
    failed_records = [
        {"name": issue.file or "unknown", "code": issue.code, "message": issue.message}
        for issue in issues
        if issue.severity == "error"
    ]

    can_process = bool(options.source_column) and options.source_column not in plan.canonical_columns
    if options.duplicate_mode == "keys" and not options.duplicate_key_columns:
        can_process = False
    if options.missing_column_strategy == "reject" and plan.has_missing_columns:
        can_process = False

    if not can_process:
        st.warning("Resolve the option warnings above before building a preview.")

    with st.container(border=True):
        st.markdown(
            f"**Planned behavior:** {MISSING_STRATEGY_LABELS[options.missing_column_strategy]} · "
            f"{DUPLICATE_MODE_LABELS[options.duplicate_mode]} · "
            f"source column `{options.source_column}`"
        )
        if st.button(
            "Build preview",
            type="primary",
            width="stretch",
            disabled=not can_process,
        ):
            st.session_state.preview = None
            st.session_state.preview_signature = None
            st.session_state.export_data = None
            st.session_state.export_signature = None
            with st.spinner("Consolidating a preview..."):
                try:
                    result = consolidate(files, plan, options)
                except MergeMateError as exc:
                    st.error(f"Could not build the preview: {exc}")
                else:
                    st.session_state.preview = result
                    st.session_state.preview_signature = current_signature
                    st.success("Preview built. Review the rows before exporting.")
        st.caption("A preview is held in memory; no files are written until you export.")

    preview = st.session_state.preview
    if preview is None or st.session_state.preview_signature != current_signature:
        st.info("Build a preview to inspect the consolidated rows and source counts.")
        return

    metrics = st.columns(4)
    metrics[0].metric("Input rows", f"{sum(file.row_count for file in files):,}")
    metrics[1].metric("Output rows", f"{preview.output_row_count:,}")
    metrics[2].metric("Files", len(files))
    metrics[3].metric("Duplicates removed", f"{preview.duplicates.get('rows_removed', 0):,}")

    st.markdown("#### Consolidated preview")
    st.dataframe(
        display_frame(preview.dataframe.head(PREVIEW_ROWS)),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        f"Showing first {min(PREVIEW_ROWS, preview.output_row_count)} of "
        f"{preview.output_row_count:,} rows · {preview.output_column_count} columns"
    )

    source_summary = pd.DataFrame(
        [
            {
                "Source file": name,
                "Input rows": preview.input_row_counts.get(name, 0),
                "Output rows": count,
            }
            for name, count in preview.output_source_counts.items()
        ]
    )
    st.markdown("#### Rows by source file")
    st.dataframe(source_summary, hide_index=True, width="stretch")

    if preview.conversions:
        st.caption(
            "Conversion operations: "
            + ", ".join(
                f"{item['column']} ({item['operation'].replace('_', ' ')})"
                for item in preview.conversions
            )
        )

    if st.button("Run consolidation and export", type="primary", width="stretch"):
        with st.spinner("Writing the Excel workbook and reports..."):
            try:
                base_name = make_output_base_name()
                report = build_report(
                    preview,
                    files,
                    issues=issues,
                    failed_files=failed_records,
                )
                written = export_all(
                    preview,
                    report,
                    Path("output"),
                    base_name,
                    report_formats="both",
                )
            except MergeMateError as exc:
                st.error(f"Export failed: {exc}")
            except Exception as exc:  # keep unexpected failures visible and actionable
                st.error(f"Unexpected export error: {exc}")
            else:
                st.session_state.export_data = {
                    "paths": written,
                    "report": report,
                    "base_name": base_name,
                    "signature": current_signature,
                }
                st.session_state.export_signature = current_signature

    export_data = st.session_state.export_data
    if export_data is None or st.session_state.export_signature != current_signature:
        st.info("The workbook has not been written yet. Run the export when the preview looks right.")
        return

    report = export_data["report"]
    written = export_data["paths"]
    st.success(
        f"Consolidation complete — {preview.output_row_count:,} rows written from "
        f"{len(files)} file(s)."
    )
    summary_metrics = st.columns(5)
    summary_metrics[0].metric("Input rows", f"{sum(file.row_count for file in files):,}")
    summary_metrics[1].metric("Output rows", f"{preview.output_row_count:,}")
    summary_metrics[2].metric("Files processed", f"{len(files)}")
    summary_metrics[3].metric("Duplicates removed", f"{preview.duplicates.get('rows_removed', 0):,}")
    summary_metrics[4].metric("Duration", f"{preview.processing_seconds:.2f}s")

    st.markdown("#### Downloads")
    download_columns = st.columns(4)
    download_specs = [
        ("excel", "Excel workbook", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("csv", "Consolidated CSV", "text/csv"),
        ("report_json", "Report JSON", "application/json"),
        ("report_csv", "Report CSV", "text/csv"),
    ]
    for column, (key, label, mime) in zip(download_columns, download_specs, strict=True):
        path = written.get(key)
        if not path or not path.exists():
            continue
        with column:
            st.download_button(
                label,
                data=path.read_bytes(),
                file_name=path.name,
                mime=mime,
                width="stretch",
            )
    st.caption(
        "Files are saved in the local output/ folder. The workbook contains "
        "Consolidated Data, Processing Summary, Column Mapping, and Validation Issues."
    )
    st.markdown(
        '<div class="mm-note">Exporting a new workbook does not preserve macros, '
        "advanced formatting, formulas, charts, or other specialized features from "
        "the original files. MergeMate writes values into a fresh workbook.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### Processing summary")
    summary_table = pd.DataFrame(
        [
            {
                "Source file": file.display_name,
                "Type": file.file_type,
                "Input rows": file.row_count,
                "Output rows": preview.output_source_counts.get(file.display_name, 0),
                "Status": "Processed",
            }
            for file in files
        ]
    )
    st.dataframe(summary_table, hide_index=True, width="stretch")

    with st.expander("Validation & duplicate details", expanded=False):
        duplicate_rows = [
            ("Policy", DUPLICATE_MODE_LABELS[preview.options.duplicate_mode]),
            ("Exact duplicates detected", preview.duplicates.get("exact_duplicates_detected", 0)),
            ("Rows removed", preview.duplicates.get("rows_removed", 0)),
            ("Rows before", preview.duplicates.get("rows_before", 0)),
            ("Rows after", preview.duplicates.get("rows_after", 0)),
        ]
        if preview.options.duplicate_mode == "keys":
            duplicate_rows.append(("Key columns", ", ".join(preview.options.duplicate_key_columns)))
            duplicate_rows.append(("Keep strategy", preview.options.duplicate_keep))
        st.markdown("**Duplicate handling**")
        st.dataframe(
            pd.DataFrame(
                [(label, str(value)) for label, value in duplicate_rows],
                columns=["Item", "Value"],
            ),
            hide_index=True,
            width="stretch",
        )

        st.markdown("**Validation issues**")
        issue_rows = report.get("validation_issues", [])
        if issue_rows:
            st.dataframe(pd.DataFrame(issue_rows), hide_index=True, width="stretch")
        else:
            st.caption("No validation issues were recorded.")

        if preview.conversions:
            st.markdown("**Type conversions**")
            st.dataframe(
                display_frame(pd.DataFrame(preview.conversions)),
                hide_index=True,
                width="stretch",
            )

        st.markdown("**Mapping applied**")
        st.dataframe(
            pd.DataFrame(report["columns"]["mapping"]),
            hide_index=True,
            width="stretch",
        )


def main() -> None:
    init_state()
    inject_css()
    read_options = render_sidebar()
    render_hero()

    result = render_file_step(read_options)
    if result is None:
        st.divider()
        st.caption(
            "MergeMate is a local portfolio project. It uses the same consolidation "
            "engine in the Streamlit interface and the CLI."
        )
        return

    files, issues, paths, sheet_overrides = result
    st.divider()
    plan, strategy = render_mapping_step(files)
    if plan is None:
        return

    st.divider()
    options = render_options_step(plan, strategy)

    st.divider()
    current_signature = _signature(
        paths, sheet_overrides, st.session_state.mapping_overrides, options, plan
    )
    if st.session_state.last_signature != current_signature:
        st.session_state.last_signature = current_signature
        clear_processing_state()

    render_preview_and_export(
        files,
        plan,
        options,
        issues,
        current_signature,
    )
    st.divider()
    st.caption(
        "MergeMate · local-first spreadsheet consolidation · "
        "original inputs are never modified."
    )


main()

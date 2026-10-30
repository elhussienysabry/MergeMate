"""Shared configuration and constants for MergeMate."""

from __future__ import annotations

from pathlib import Path

APP_NAME = "MergeMate"
APP_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_INPUT_DIR = PROJECT_ROOT / "data" / "sample_inputs"
DEFAULT_OUTPUT_DIR = Path("output")

SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}

# Deliberately modest local limits: MergeMate is designed for everyday
# spreadsheet consolidation, not large-scale data engineering workloads.
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB per input file
MAX_ROWS_PER_FILE = 50_000
MAX_TOTAL_ROWS = 200_000
MAX_COLUMNS = 200
MAX_FILES = 20

DEFAULT_SOURCE_COLUMN = "Source_File"
PREVIEW_ROWS = 20

MISSING_STRATEGIES = ("blank", "exclude", "reject")
DUPLICATE_MODES = ("keep_all", "exact", "keys")
DUPLICATE_KEEP = ("first", "last")

MISSING_STRATEGY_LABELS = {
    "blank": "Fill missing columns with blanks",
    "exclude": "Exclude columns that are not in every file",
    "reject": "Reject files with missing columns",
}

DUPLICATE_MODE_LABELS = {
    "keep_all": "Keep all records",
    "exact": "Remove exact duplicate rows",
    "keys": "Remove duplicates using selected key columns",
}

CSV_DELIMITER_OPTIONS = {
    "auto": None,
    "comma": ",",
    "semicolon": ";",
    "tab": "\t",
    "pipe": "|",
}

CSV_ENCODING_OPTIONS = {
    "auto": None,
    "utf-8": "utf-8",
    "utf-8-sig": "utf-8-sig",
    "latin-1": "latin-1",
}

CSV_DECIMAL_OPTIONS = {
    "auto": None,
    "dot": ".",
    "comma": ",",
}

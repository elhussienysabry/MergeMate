"""Column-name normalization, mapping plans, and compatibility checks."""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from mergemate.exceptions import MappingError
from mergemate.file_readers import LoadedFile


def normalize_column_name(name: object) -> str:
    """Create a stable, readable snake_case key from a spreadsheet header.

    The transformation only affects the header, never the data values.
    """
    text = str(name).replace("\ufeff", "").strip()
    text = re.sub(r"[^\w]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("_").lower()
    if not text:
        raise MappingError(
            f"Column header '{name}' cannot be normalized. Give the column a name."
        )
    return text


@dataclass
class FileColumnMapping:
    """The mapping chosen for one input file."""

    file_name: str
    source_headers: list[str]
    normalized_headers: dict[str, str]
    source_to_output: dict[str, str]
    ignored_columns: list[str]
    missing_columns: list[str] = field(default_factory=list)
    file_specific_columns: list[str] = field(default_factory=list)
    suggestions: dict[str, list[str]] = field(default_factory=dict)

    @property
    def mapped_output_columns(self) -> list[str]:
        return list(self.source_to_output.values())

    def source_for_output(self, output_column: str) -> str | None:
        for source, target in self.source_to_output.items():
            if target == output_column:
                return source
        return None


@dataclass
class ColumnMappingPlan:
    """The complete proposed mapping for all input files."""

    canonical_columns: list[str]
    common_columns: list[str]
    file_mappings: dict[str, FileColumnMapping]
    warnings: list[str] = field(default_factory=list)

    @property
    def files(self) -> list[str]:
        return list(self.file_mappings)

    @property
    def missing_columns_by_file(self) -> dict[str, list[str]]:
        return {
            name: mapping.missing_columns
            for name, mapping in self.file_mappings.items()
            if mapping.missing_columns
        }

    @property
    def file_specific_columns_by_file(self) -> dict[str, list[str]]:
        return {
            name: mapping.file_specific_columns
            for name, mapping in self.file_mappings.items()
            if mapping.file_specific_columns
        }

    @property
    def ignored_columns_by_file(self) -> dict[str, list[str]]:
        return {
            name: mapping.ignored_columns
            for name, mapping in self.file_mappings.items()
            if mapping.ignored_columns
        }

    @property
    def has_missing_columns(self) -> bool:
        return any(mapping.missing_columns for mapping in self.file_mappings.values())

    def header_differences(self) -> list[dict[str, str]]:
        differences: list[dict[str, str]] = []
        for file_name, mapping in self.file_mappings.items():
            for source, output in mapping.source_to_output.items():
                if source != output:
                    differences.append(
                        {
                            "file": file_name,
                            "source_header": source,
                            "output_column": output,
                        }
                    )
        return differences

    def mapping_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for file_name, mapping in self.file_mappings.items():
            for source in mapping.source_headers:
                output = mapping.source_to_output.get(source)
                if output:
                    status = "mapped"
                    note = "header normalized" if source != output else ""
                else:
                    status = "ignored"
                    note = "excluded from output by the user"
                rows.append(
                    {
                        "file": file_name,
                        "source_header": source,
                        "output_column": output or "",
                        "status": status,
                        "note": note,
                    }
                )
        return rows

    def suggestions(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for file_name, mapping in self.file_mappings.items():
            for source, candidates in mapping.suggestions.items():
                for candidate in candidates:
                    rows.append(
                        {
                            "file": file_name,
                            "source_header": source,
                            "suggested_output": candidate,
                        }
                    )
        return rows


def _validate_overrides(
    files: list[LoadedFile],
    overrides: dict[str, dict[str, str | None]],
    ignored_columns: dict[str, Iterable[str]],
) -> None:
    known_files = {file.display_name for file in files}
    for file_name in set(overrides) | set(ignored_columns):
        if file_name not in known_files:
            raise MappingError(
                f"Mapping refers to unknown file '{file_name}'. "
                f"Known files: {', '.join(sorted(known_files))}."
            )
    by_file = {file.display_name: set(file.columns) for file in files}
    for file_name, mapping in overrides.items():
        for source in mapping:
            if source not in by_file[file_name]:
                raise MappingError(
                    f"Mapping refers to column '{source}', which is not present in "
                    f"'{file_name}'."
                )
    for file_name, ignored in ignored_columns.items():
        for source in ignored:
            if source not in by_file[file_name]:
                raise MappingError(
                    f"Ignored column '{source}' is not present in '{file_name}'."
                )


def build_mapping_plan(
    files: list[LoadedFile],
    *,
    overrides: dict[str, dict[str, str | None]] | None = None,
    ignored_columns: dict[str, Iterable[str]] | None = None,
) -> ColumnMappingPlan:
    """Build an explicit, reviewable mapping plan.

    Exact normalized headers are mapped automatically. Headers that are not
    identical after normalization are never merged without an explicit
    override. Similar names are only surfaced as suggestions.
    """
    if not files:
        raise MappingError("At least one readable input file is required.")
    overrides = overrides or {}
    ignored_columns = {
        file_name: set(columns)
        for file_name, columns in (ignored_columns or {}).items()
    }
    _validate_overrides(files, overrides, ignored_columns)

    normalized_by_file: dict[str, dict[str, str]] = {}
    canonical_columns: list[str] = []
    seen_canonical: set[str] = set()

    for loaded in files:
        normalized: dict[str, str] = {}
        for source in loaded.columns:
            key = normalize_column_name(source)
            if key in normalized.values():
                collision = next(
                    existing for existing, value in normalized.items() if value == key
                )
                raise MappingError(
                    f"'{loaded.display_name}' has headers '{collision}' and '{source}' "
                    f"that both normalize to '{key}'. Rename one header or map it "
                    "explicitly."
                )
            normalized[source] = key
            if key not in seen_canonical:
                seen_canonical.add(key)
                canonical_columns.append(key)
        normalized_by_file[loaded.display_name] = normalized

    for loaded in files:
        for target in overrides.get(loaded.display_name, {}).values():
            if target in (None, ""):
                continue
            key = normalize_column_name(target)
            if key not in seen_canonical:
                seen_canonical.add(key)
                canonical_columns.append(key)

    file_mappings: dict[str, FileColumnMapping] = {}
    warnings: list[str] = []
    for loaded in files:
        name = loaded.display_name
        normalized = normalized_by_file[name]
        ignored = set(ignored_columns.get(name, set()))
        file_overrides = overrides.get(name, {})
        source_to_output: dict[str, str] = {}
        final_ignored: list[str] = []

        for source in loaded.columns:
            if source in ignored:
                final_ignored.append(source)
                continue
            if source in file_overrides:
                target = file_overrides[source]
                if target in (None, ""):
                    final_ignored.append(source)
                    continue
                output = normalize_column_name(target)
            else:
                output = normalized[source]
            source_to_output[source] = output

        targets = list(source_to_output.values())
        if len(set(targets)) != len(targets):
            duplicates = sorted({target for target in targets if targets.count(target) > 1})
            raise MappingError(
                f"More than one column in '{name}' maps to: {', '.join(duplicates)}. "
                "Choose a different output column for each source column."
            )

        file_mappings[name] = FileColumnMapping(
            file_name=name,
            source_headers=loaded.columns,
            normalized_headers=normalized,
            source_to_output=source_to_output,
            ignored_columns=final_ignored,
        )

    mapped_anywhere = {
        target
        for mapping in file_mappings.values()
        for target in mapping.mapped_output_columns
    }
    unused_columns = [column for column in canonical_columns if column not in mapped_anywhere]
    if unused_columns:
        warnings.append(
            "Columns with no mapped source were excluded: "
            + ", ".join(unused_columns)
            + "."
        )
        canonical_columns = [
            column for column in canonical_columns if column in mapped_anywhere
        ]
    if not canonical_columns:
        raise MappingError("No columns remain after applying the mapping.")

    common_columns = [
        column
        for column in canonical_columns
        if all(
            column in mapping.mapped_output_columns
            for mapping in file_mappings.values()
        )
    ]

    other_columns = set(canonical_columns)
    for name, mapping in file_mappings.items():
        mapping.missing_columns = [
            column for column in canonical_columns if column not in mapping.mapped_output_columns
        ]
        mapping.file_specific_columns = [
            column
            for column in mapping.mapped_output_columns
            if column not in common_columns
        ]
        suggestions: dict[str, list[str]] = {}
        for source, output in mapping.source_to_output.items():
            candidates = difflib.get_close_matches(
                output,
                sorted(other_columns - {output}),
                n=2,
                cutoff=0.78,
            )
            if candidates:
                suggestions[source] = candidates
        mapping.suggestions = suggestions
        if mapping.missing_columns:
            warnings.append(
                f"'{name}' is missing column(s): {', '.join(mapping.missing_columns)}."
            )

    return ColumnMappingPlan(
        canonical_columns=canonical_columns,
        common_columns=common_columns,
        file_mappings=file_mappings,
        warnings=warnings,
    )

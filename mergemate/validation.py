"""Small validation primitives shared by the CLI, UI, and tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SEVERITIES = ("info", "warning", "error")


@dataclass(frozen=True)
class ValidationIssue:
    """A non-fatal or fatal issue detected while handling input data.

    Messages intentionally describe columns and counts rather than row
    contents. This keeps reports useful without copying sensitive values.
    """

    severity: str
    code: str
    message: str
    file: str | None = None
    details: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"Unknown severity: {self.severity}")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.file:
            data["file"] = self.file
        if self.details:
            data["details"] = self.details
        return data


def issues_to_dicts(issues: list[ValidationIssue]) -> list[dict[str, Any]]:
    return [issue.to_dict() for issue in issues]


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)

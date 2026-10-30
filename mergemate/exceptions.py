"""Domain exceptions with user-facing messages."""

from __future__ import annotations


class MergeMateError(Exception):
    """Base class for expected MergeMate errors."""


class InputValidationError(MergeMateError):
    """An input file cannot be used."""


class UnsupportedFileTypeError(InputValidationError):
    """The file extension is not supported."""


class EmptyFileError(InputValidationError):
    """The file or selected worksheet has no data."""


class FileTooLargeError(InputValidationError):
    """The file exceeds the configured size limit."""


class TooManyRowsError(InputValidationError):
    """The file exceeds the configured row limit."""


class TooManyColumnsError(InputValidationError):
    """The file exceeds the configured column limit."""


class WorksheetError(InputValidationError):
    """The requested worksheet is missing or unreadable."""


class MalformedFileError(InputValidationError):
    """The file cannot be parsed safely."""


class MappingError(MergeMateError):
    """A column mapping is invalid."""


class IncompatibleFilesError(MergeMateError):
    """Files cannot be combined under the selected schema policy."""


class ConsolidationError(MergeMateError):
    """The consolidation options are invalid."""


class ExportError(MergeMateError):
    """An output file could not be written."""

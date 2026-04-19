"""Custom exception hierarchy for Plant Savior.

Using typed exceptions lets callers handle failure modes explicitly
instead of catching bare ``Exception``.
"""


class PlantSaviorError(Exception):
    """Base class for all Plant Savior errors."""


class PlantNotFoundError(PlantSaviorError):
    """Raised when a plant lookup by ID returns no row."""


class CalendarServiceError(PlantSaviorError):
    """Raised when a Google Calendar API call fails."""


class CalendarAuthError(CalendarServiceError):
    """Raised when Google Calendar credentials are missing or invalid."""

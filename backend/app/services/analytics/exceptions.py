class AnalyticsError(Exception):
    """Base exception for analytics and reporting errors."""


class InvalidDateRangeError(AnalyticsError):
    """Raised when start_date is after end_date."""


class InvalidAnalyticsFilterError(AnalyticsError):
    """Raised when filter parameters are invalid or unsupported."""


class ReportNotFoundError(AnalyticsError):
    """Raised when a requested report metadata or file is not found."""


class ReportGenerationError(AnalyticsError):
    """Raised when PDF report generation fails."""


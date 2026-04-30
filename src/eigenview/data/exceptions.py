from __future__ import annotations


class DataNotFoundError(Exception):
    """Raised when no data is returned for a requested ticker/timeframe."""


class DataStaleError(Exception):
    """Raised when cached data exceeds its freshness threshold."""


class RateLimitError(Exception):
    """Raised when an external API returns a rate-limit response."""

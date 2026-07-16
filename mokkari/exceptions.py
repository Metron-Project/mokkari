"""Exceptions module.

This module provides the following classes:

- ApiError: General API errors, authentication failures, or network issues
- RateLimitError: Raised when API rate limits are exceeded
- AuthenticationError: Missing or invalid authentication credentials
- CacheError: Errors related to cache operations
"""

from __future__ import annotations


class ApiError(Exception):
    """Class for any api errors."""

    def __init__(self: ApiError, *args, **kwargs: dict[str, any]) -> None:
        """Initialize an ApiError."""
        Exception.__init__(self, *args, **kwargs)


class RateLimitError(Exception):
    """Exception raised when API rate limits are exceeded.

    This exception is raised when either the fixed per-minute burst limit (20
    requests) or the per-day sustained limit is exceeded. The sustained limit
    varies per user — it's 5,000/day by default, higher for OpenCollective
    donors — so mokkari doesn't know it in advance; it's read from the
    ``X-RateLimit-*`` headers Metron returns with each response. The exception
    message includes:
    - Which rate limit was exceeded (minute or day)
    - The specific limit value, as last reported by Metron
    - Human-readable wait time before the next request can be made

    Session pre-empts requests locally once the most recently observed
    headers show a window is exhausted, avoiding an HTTP call that would fail
    on the server side anyway.

    Attributes:
        retry_after: Number of seconds to wait before the next request can be made.
                     This allows applications to implement programmatic retry logic.

    Note:
        Applications should catch this exception and implement appropriate retry
        logic or inform users about the rate limit. See the Session class
        documentation for examples of handling this exception.

    Examples:
        >>> from mokkari import Session
        >>> from mokkari.exceptions import RateLimitError
        >>> import time
        >>> session = Session("username", "password")
        >>> try:
        ...     issue = session.issue(1)
        ... except RateLimitError as e:
        ...     # Error message format:
        ...     # "Rate limit exceeded: You have reached the 20 requests per minute limit.
        ...     #  Please wait 1 minute, 30 seconds before making another request."
        ...     print(f"Rate limited: {e}")
        ...     # Access the numeric delay value for programmatic retry
        ...     time.sleep(e.retry_after)
    """

    def __init__(
        self: RateLimitError,
        message: str,
        retry_after: float = 0,
    ) -> None:
        """Initialize a RateLimitError.

        Args:
            message: The error message describing the rate limit condition.
            retry_after: Number of seconds to wait before the next request (default: 0).
        """
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(Exception):
    """Class for any authentication errors."""

    def __init__(self: AuthenticationError) -> None:
        """Initialize the Authentication error."""
        Exception.__init__(self, "Missing authorization information")


class CacheError(Exception):
    """Class for any database cache errors."""

    def __init__(self: CacheError, *args, **kwargs: dict[str, any]) -> None:
        """Initialize an CacheError."""
        Exception.__init__(self, *args, **kwargs)

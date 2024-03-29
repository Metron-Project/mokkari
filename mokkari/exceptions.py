# ruff: noqa: ANN002
"""Exceptions module.

This module provides the following classes:

- ApiError
- AuthenticationError
- CacheError
"""


class ApiError(Exception):
    """Class for any api errors."""

    def __init__(self: "ApiError", *args, **kwargs: dict[str, any]) -> None:
        """Initialize an ApiError."""
        Exception.__init__(self, *args, **kwargs)


class AuthenticationError(Exception):
    """Class for any authentication errors."""

    def __init__(self: "AuthenticationError") -> None:
        """Initialize the Authentication error."""
        Exception.__init__(self, "Missing authorization information")


class CacheError(Exception):
    """Class for any database cache errors."""

    def __init__(self: "CacheError", *args, **kwargs: dict[str, any]) -> None:
        """Initialize an CacheError."""
        Exception.__init__(self, *args, **kwargs)

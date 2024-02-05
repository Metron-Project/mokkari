"""
Exceptions module.

This module provides the following classes:

- ApiError
- AuthenticationError
- CacheError
"""


class ApiError(Exception):
    """Class for any api errors."""

    def __init__(self: "ApiError", *args: tuple[any], **kwargs: dict[str, any]) -> None:
        """Initialize an ApiError."""
        Exception.__init__(self, *args, **kwargs)


class AuthenticationError(Exception):
    """Class for any authentication errors."""

    def __init__(self: "AuthenticationError", *args: tuple[any], **kwargs: dict[str, any]) -> None:
        """Initialize an AuthenticationError."""
        Exception.__init__(self, *args, **kwargs)


class CacheError(Exception):
    """Class for any database cache errors."""

    def __init__(self: "CacheError", *args: tuple[any], **kwargs: dict[str, any]) -> None:
        """Initialize an CacheError."""
        Exception.__init__(self, *args, **kwargs)

"""
Exceptions module.

This module provides the following classes:

- ApiError
- AuthenticationError
- CacheError
"""


class ApiError(Exception):
    """Class for any api errors."""

    def __init__(self, *args, **kwargs):
        """Initialize an ApiError."""
        Exception.__init__(self, *args, **kwargs)


class AuthenticationError(ApiError):
    """Class for any authentication errors."""

    def __init__(self, *args, **kwargs):
        """Initialize an AuthenticationError."""
        Exception.__init__(self, *args, **kwargs)


class CacheError(ApiError):
    """Class for any database cache errors."""

    def __init__(self, *args, **kwargs):
        """Initialize an CacheError."""
        Exception.__init__(self, *args, **kwargs)

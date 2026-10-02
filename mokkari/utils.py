"""Utilities module.

This module provides the following functions:

- format_time: Format a number of seconds as a human-readable duration

It imports nothing from the rest of ``mokkari``, so any module can use it without
creating a circular import.
"""

from __future__ import annotations

from typing import Final

__all__ = ["format_time"]

SECONDS_PER_HOUR: Final[int] = 3_600
SECONDS_PER_MINUTE: Final[int] = 60


def format_time(seconds: str | float) -> str:
    """Format seconds into a verbose human-readable time string.

    Args:
        seconds: Number of seconds to format. Can be a string or float.

    Returns:
        str: Formatted time string (e.g., "2 hours, 30 minutes, 45 seconds").

    Examples:
        >>> format_time(3661)
        "1 hour, 1 minute, 1 second"
        >>> format_time(90)
        "1 minute, 30 seconds"
        >>> format_time(0)
        "0 seconds"
    """
    total_seconds = int(seconds)

    if total_seconds < 0:
        return "0 seconds"

    hours = total_seconds // SECONDS_PER_HOUR
    minutes = (total_seconds % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE
    remaining_seconds = total_seconds % SECONDS_PER_MINUTE

    parts = []

    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")

    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

    if remaining_seconds > 0 or not parts:
        parts.append(f"{remaining_seconds} second{'s' if remaining_seconds != 1 else ''}")

    return ", ".join(parts)

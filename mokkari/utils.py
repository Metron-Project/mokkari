"""Utilities module.

This module provides the following functions:

- format_time: Format a number of seconds as a human-readable duration
- hamming_distance: Count the bits that differ between two cover hashes
- is_cover_hash: Check whether a string is a 64-bit cover hash

It imports nothing from the rest of ``mokkari``, so any module can use it without
creating a circular import.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = [
    "DEFAULT_COVER_HASH_DISTANCE",
    "MAX_COVER_HASH_DISTANCE",
    "format_time",
    "hamming_distance",
    "is_cover_hash",
]

SECONDS_PER_HOUR: Final[int] = 3_600
SECONDS_PER_MINUTE: Final[int] = 60

# The Hamming distance Metron's cover-hash search uses when none is given, and the
# widest it allows. These mirror Metron's current server-side limits for reference;
# mokkari doesn't enforce them, so Metron stays the authority if it changes them.
DEFAULT_COVER_HASH_DISTANCE: Final[int] = 10
MAX_COVER_HASH_DISTANCE: Final[int] = 20

# A 64-bit perceptual hash, as Metron stores and takes it.
_COVER_HASH_RE: Final[re.Pattern[str]] = re.compile(r"[0-9a-fA-F]{16}")


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


def is_cover_hash(value: str) -> bool:
    """Check whether a string is a 64-bit perceptual hash, as 16 hex digits.

    Args:
        value: The string to check. It must be exactly 16 hex digits, in either case,
            with no surrounding whitespace.

    Returns:
        bool: ``True`` if ``value`` is 16 hex digits, otherwise ``False``.

    Examples:
        >>> is_cover_hash("c3a1e1f0f8d8c0c0")
        True
        >>> is_cover_hash("abc123")
        False
    """
    return _COVER_HASH_RE.fullmatch(value) is not None


def hamming_distance(a: str, b: str) -> int | None:
    """Count the bits that differ between two cover hashes.

    Args:
        a: A 64-bit perceptual hash as 16 hex digits.
        b: Another.

    Returns:
        int | None: The number of differing bits, 0 to 64, or ``None`` if either isn't
        16 hex digits.

    Examples:
        >>> hamming_distance("ffffffffffffffff", "fffffffffffffffe")
        1
        >>> hamming_distance("ffffffffffffffff", "") is None
        True
    """
    if not (is_cover_hash(a) and is_cover_hash(b)):
        return None
    return (int(a, 16) ^ int(b, 16)).bit_count()

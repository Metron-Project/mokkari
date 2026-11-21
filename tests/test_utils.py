"""Test Utils module.

This module contains tests for the format_time and hamming_distance helpers.
"""

import pytest

from mokkari.utils import format_time, hamming_distance


def test_format_time_minutes_and_seconds() -> None:
    """format_time formats a sub-hour delay as minutes and seconds."""
    assert format_time(90.5) == "1 minute, 30 seconds"


def test_format_time_hours() -> None:
    """format_time formats a multi-hour delay correctly."""
    assert format_time(9_000) == "2 hours, 30 minutes"


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("c3a1e1f0f8d8c0c0", "c3a1e1f0f8d8c0c0", 0),
        ("c3a1e1f0f8d8c0c0", "C3A1E1F0F8D8C0C3", 2),
        ("0000000000000000", "ffffffffffffffff", 64),
        ("c3a1e1f0f8d8c0c0", "", None),
        ("c3a1e1f0f8d8c0c0", "abc123", None),
        ("c3a1e1f0f8d8c0cg", "c3a1e1f0f8d8c0c0", None),
        ("c3a1e1f0f8d8c0c0 ", "c3a1e1f0f8d8c0c0", None),
    ],
)
def test_hamming_distance(a: str, b: str, expected: int | None) -> None:
    """hamming_distance counts differing bits, or returns None for a malformed hash."""
    assert hamming_distance(a, b) == expected

"""Test Utils module.

This module contains tests for the format_time helper.
"""

from mokkari.utils import format_time


def test_format_time_minutes_and_seconds() -> None:
    """format_time formats a sub-hour delay as minutes and seconds."""
    assert format_time(90.5) == "1 minute, 30 seconds"


def test_format_time_hours() -> None:
    """format_time formats a multi-hour delay correctly."""
    assert format_time(9_000) == "2 hours, 30 minutes"

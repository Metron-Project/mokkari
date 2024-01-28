"""
Test Series Type.

This module contains tests for SeriesType objects.
"""

from mokkari.session import Session


def test_series_type_list(talker: Session) -> None:
    """Test the SeriesTypeList."""
    series_types = talker.series_type_list()
    st_iter = iter(series_types)
    assert next(st_iter).name == "Annual Series"
    assert next(st_iter).name == "Cancelled Series"
    assert series_types[3].name == "Hard Cover"
    assert len(series_types) == 8

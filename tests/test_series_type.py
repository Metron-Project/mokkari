"""Test Series Type.

This module contains tests for SeriesType objects.
"""

from mokkari.session import Session


def test_series_type_list(talker: Session) -> None:
    """Test the SeriesTypeList."""
    series_types = talker.series_type_list()
    st_iter = iter(series_types)
    assert next(st_iter).name == "Annual"
    assert next(st_iter).name == "Digital Chapter"
    assert series_types[3].name == "Hardcover"
    assert len(series_types) == 9

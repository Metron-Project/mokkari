"""
Test Series module.

This module contains tests for Series objects.
"""
import pytest
import requests_mock

from mokkari import exceptions, series_list


def test_known_series(talker):
    """Test for a known series."""
    death = talker.series(1)
    assert death.name == "Death of the Inhumans"
    assert death.sort_name == "Death of the Inhumans"
    assert death.volume == 1
    assert death.year_began == 2018
    assert death.year_end == 2018
    assert death.issue_count == 5
    assert death.image == "https://static.metron.cloud/media/issue/2018/11/11/6497376-01.jpg"
    assert death.series_type.name == "Mini-Series"
    assert death.publisher_id == 1


def test_series_without_year_end(talker):
    """Test for series without a year-end date."""
    abs_carnage = talker.series(2311)
    assert abs_carnage.name == "Absolute Carnage"
    assert abs_carnage.sort_name == "Absolute Carnage"
    assert abs_carnage.volume == 1
    assert abs_carnage.year_began == 2019
    assert abs_carnage.year_end is None
    assert abs_carnage.issue_count == 5
    assert abs_carnage.publisher_id == 1
    assert abs_carnage.series_type.name == "Mini-Series"


def test_serieslist(talker):
    """Test the SeriesList."""
    series = talker.series_list()
    series_iter = iter(series)
    assert next(series_iter).id == 2354
    assert next(series_iter).id == 1530
    assert next(series_iter).id == 1531
    assert next(series_iter).id == 1532
    assert len(series) == 28
    assert series[3].id == 1532
    assert (
        series[3].display_name == "100ᵗʰ Anniversary Special: Guardians of the Galaxy (2014)"
    )


def test_bad_series(talker):
    """Test for a non-existant series."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/series/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.series(-1)


def test_bad_response_data():
    """Test for a bad series response."""
    with pytest.raises(exceptions.ApiError):
        series_list.SeriesList({"results": {"name": 1}})

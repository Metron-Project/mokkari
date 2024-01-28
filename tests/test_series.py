"""
Test Series module.

This module contains tests for Series objects.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.session import Session


def test_known_series(talker: Session) -> None:
    """Test for a known series."""
    death = talker.series(1)
    assert death.name == "Death of the Inhumans"
    assert death.sort_name == "Death of the Inhumans"
    assert death.volume == 1
    assert death.year_began == 2018
    assert death.year_end == 2018
    assert death.issue_count == 5
    assert death.series_type.name == "Limited Series"
    assert death.publisher.id == 1
    assert death.publisher.name == "Marvel"
    assert death.modified == datetime(
        2023,
        10,
        23,
        16,
        58,
        50,
        526656,
        tzinfo=timezone(timedelta(days=-1, seconds=72000), "-0400"),
    )
    assert death.resource_url.__str__() == "https://metron.cloud/series/death-of-the-inhumans-2018/"


def test_series_without_year_end(talker: Session) -> None:
    """Test for series without a year-end date."""
    abs_carnage = talker.series(2311)
    assert abs_carnage.name == "Absolute Carnage"
    assert abs_carnage.sort_name == "Absolute Carnage"
    assert abs_carnage.volume == 1
    assert abs_carnage.year_began == 2019
    assert abs_carnage.year_end is None
    assert abs_carnage.issue_count == 5
    assert abs_carnage.publisher.id == 1
    assert abs_carnage.publisher.name == "Marvel"
    assert abs_carnage.series_type.name == "Limited Series"


def test_series_list(talker: Session) -> None:
    """Test the SeriesList."""
    series = talker.series_list({"name": "batman"})
    series_iter = iter(series)
    assert next(series_iter).id == 2547
    assert next(series_iter).id == 5959
    assert next(series_iter).id == 2481
    assert next(series_iter).id == 763
    assert next(series_iter).id == 93
    assert len(series) == 219
    assert series[4].id == 93
    assert series[4].display_name == "Batman (2016)"


def test_bad_series(talker: Session) -> None:
    """Test for a non-existent series."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/series/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.series(-1)


def test_bad_series_validate(talker: Session) -> None:
    """Test data with invalid data."""
    # Change the 'name' field to an int, when it should be a string.
    data = {
        "id": 150,
        "name": 50,
        "sort_name": "Gunhawks",
        "volume": 1,
        "series_type": {"id": 5, "name": "One-Shot"},
        "publisher": 1,
        "year_began": 2019,
        "year_end": 2019,
        "desc": "",
        "issue_count": 1,
        "modified": "2019-07-05T14:32:52.256872-04:00",
        "image": "https://static.metron.cloud/media/issue/2019/02/06/gunhawks-1.jpg",
    }
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/series/150/",
            text=json.dumps(data),
        )

        with pytest.raises(exceptions.ApiError):
            talker.series(150)


def test_series_with_associated_series(talker: Session) -> None:
    """Test series with an associated series link."""
    ff = talker.series(2818)
    assert ff.name == "Fantastic Four Annual"
    assert len(ff.associated) == 1
    assoc = ff.associated[0]
    assert assoc.id == 26
    assert assoc.name == "Fantastic Four (1961)"


def test_series_with_genres(talker: Session) -> None:
    """Test series with genres."""
    tt2011 = talker.series(3503)
    assert tt2011.name == "Teen Titans"
    assert len(tt2011.genres) == 1
    assert tt2011.genres[0].name == "Super-Hero"

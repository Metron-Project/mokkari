"""Test Series module.

This module contains tests for Series objects.
"""

import json
from datetime import date

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.session import Session


def test_series_with_imprint(talker: Session) -> None:
    """Test series from an imprint."""
    sandman = talker.series(3315)
    assert sandman.imprint.id == 1
    assert sandman.imprint.name == "Vertigo Comics"


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
    assert death.status == "Completed"
    assert death.publisher.id == 1
    assert death.publisher.name == "Marvel"
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
    assert abs_carnage.status == "Completed"


def test_series_list(talker: Session) -> None:
    """Test the SeriesList."""
    series = talker.series_list({"name": "batman"})
    series_iter = iter(series)
    assert next(series_iter).id == 8477
    assert next(series_iter).id == 13742
    assert next(series_iter).id == 13637
    assert next(series_iter).id == 2547
    assert next(series_iter).id == 11897
    assert len(series) == 393
    assert series[3].id == 2547
    assert series[3].volume == 1
    assert series[3].issue_count == 14
    assert series[4].id == 11897
    assert series[4].display_name == "All Star Batman & Robin, The Boy Wonder (2005)"
    assert series[4].volume == 1


def test_series_issues_list(talker: Session) -> None:
    """Test for getting an issue list for a series."""
    data = {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 1,
                "series": {"name": "Death of the Inhumans", "volume": 1, "year_began": 2018},
                "number": "1",
                "issue": "Death of the Inhumans (2018) #1",
                "cover_date": "2018-09-01",
                "store_date": "2018-07-04",
                "image": "https://static.metron.cloud/media/issue/2018/09/22/death-of-the-inhumans-1.jpg",
                "cover_hash": "abc123def456",
                "modified": "2019-06-23T15:13:19.432378-04:00",
            },
            {
                "id": 2,
                "series": {"name": "Death of the Inhumans", "volume": 1, "year_began": 2018},
                "number": "2",
                "issue": "Death of the Inhumans (2018) #2",
                "cover_date": "2018-10-01",
                "store_date": "2018-08-08",
                "image": "https://static.metron.cloud/media/issue/2018/09/22/death-of-the-inhumans-2.jpg",
                "cover_hash": "abc123def457",
                "modified": "2019-06-23T15:13:19.432378-04:00",
            },
        ],
    }
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/series/1/issue_list/",
            text=json.dumps(data),
        )
        issues = talker.series_issues_list(1)
        assert len(issues) == 2
        assert issues[0].id == 1
        assert issues[0].issue_name == "Death of the Inhumans (2018) #1"
        assert issues[0].cover_date == date(2018, 9, 1)


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

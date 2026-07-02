"""Test Series module.

This module contains tests for Series objects.
"""

import json
from datetime import date

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.schemas.series import BaseSeries, Series
from mokkari.session import Session

_MODIFIED = "2019-06-23T15:13:19.432378-04:00"

_COMMON_SERIES = {
    "id": 1,
    "volume": 1,
    "year_began": 2018,
    "issue_count": 5,
    "modified": _MODIFIED,
}

_FULL_SERIES = {
    **_COMMON_SERIES,
    "name": "Death of the Inhumans",
    "sort_name": "Death of the Inhumans",
    "series_type": {"id": 11, "name": "Limited Series"},
    "status": "Completed",
    "publisher": {"id": 1, "name": "Marvel"},
    "desc": "",
    "genres": [],
    "associated": [],
    "resource_url": "https://metron.cloud/series/death-of-the-inhumans-2018/",
}


def test_series_with_imprint() -> None:
    """Test series from an imprint."""
    sandman = Series(
        **{
            **_FULL_SERIES,
            "id": 3315,
            "name": "The Sandman",
            "sort_name": "Sandman",
            "imprint": {"id": 1, "name": "Vertigo Comics"},
            "resource_url": "https://metron.cloud/series/sandman-1989/",
        }
    )
    assert sandman.imprint.id == 1
    assert sandman.imprint.name == "Vertigo Comics"


def test_known_series() -> None:
    """Test for a known series."""
    death = Series(**{**_FULL_SERIES, "year_end": 2018})
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


def test_series_without_year_end() -> None:
    """Test for series without a year-end date."""
    abs_carnage = Series(
        **{
            **_FULL_SERIES,
            "id": 2311,
            "name": "Absolute Carnage",
            "sort_name": "Absolute Carnage",
            "year_began": 2019,
            "year_end": None,
            "resource_url": "https://metron.cloud/series/absolute-carnage-2019/",
        }
    )
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
    data = {
        "count": 3,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 8477,
                "series": "Batman (2016)",
                "volume": 1,
                "year_began": 2016,
                "year_end": None,
                "issue_count": 125,
                "modified": _MODIFIED,
            },
            {
                "id": 2547,
                "series": "Batman (1940)",
                "volume": 1,
                "year_began": 1940,
                "year_end": 2011,
                "issue_count": 14,
                "modified": _MODIFIED,
            },
            {
                "id": 11897,
                "series": "All Star Batman & Robin, The Boy Wonder (2005)",
                "volume": 1,
                "year_began": 2005,
                "year_end": None,
                "issue_count": 10,
                "modified": _MODIFIED,
            },
        ],
    }
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/series/", text=json.dumps(data))
        series = talker.series_list({"name": "batman"})
    series_iter = iter(series)
    assert next(series_iter).id == 8477
    assert next(series_iter).id == 2547
    assert next(series_iter).id == 11897
    assert len(series) == 3
    assert series[1].id == 2547
    assert series[1].volume == 1
    assert series[1].issue_count == 14
    assert series[2].id == 11897
    assert series[2].display_name == "All Star Batman & Robin, The Boy Wonder (2005)"
    assert series[2].volume == 1


def test_series_issues_list(talker: Session) -> None:
    """Test for getting an issue list for a series."""
    data = {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 1,
                "series": {
                    "id": 1,
                    "name": "Death of the Inhumans",
                    "volume": 1,
                    "year_began": 2018,
                },
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
                "series": {
                    "id": 1,
                    "name": "Death of the Inhumans",
                    "volume": 1,
                    "year_began": 2018,
                },
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


def test_series_with_associated_series() -> None:
    """Test series with an associated series link."""
    ff = Series(
        **{
            **_FULL_SERIES,
            "id": 2818,
            "name": "Fantastic Four Annual",
            "sort_name": "Fantastic Four Annual",
            "year_began": 1963,
            "associated": [{"id": 26, "series": "Fantastic Four (1961)"}],
            "resource_url": "https://metron.cloud/series/fantastic-four-annual-1963/",
        }
    )
    assert ff.name == "Fantastic Four Annual"
    assert len(ff.associated) == 1
    assert ff.associated[0].id == 26
    assert ff.associated[0].name == "Fantastic Four (1961)"


def test_series_with_genres() -> None:
    """Test series with genres."""
    tt2011 = Series(
        **{
            **_FULL_SERIES,
            "id": 3503,
            "name": "Teen Titans",
            "sort_name": "Teen Titans",
            "year_began": 2011,
            "genres": [{"id": 10, "name": "Super-Hero"}],
            "resource_url": "https://metron.cloud/series/teen-titans-2011/",
        }
    )
    assert tt2011.name == "Teen Titans"
    assert len(tt2011.genres) == 1
    assert tt2011.genres[0].name == "Super-Hero"


def test_series_list_with_year_end() -> None:
    """Test that year_end is returned correctly in a series list."""
    series = BaseSeries(
        id=1,
        series="Death of the Inhumans (2018)",
        volume=1,
        year_began=2018,
        year_end=2018,
        issue_count=5,
        modified=_MODIFIED,
    )
    assert series.year_end == 2018


def test_series_list_without_year_end() -> None:
    """Test that year_end is None when absent from a series list entry."""
    series = BaseSeries(
        id=2311,
        series="Absolute Carnage (2019)",
        volume=1,
        year_began=2019,
        year_end=None,
        issue_count=5,
        modified=_MODIFIED,
    )
    assert series.year_end is None

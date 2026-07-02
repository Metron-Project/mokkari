"""Test Arcs module.

This module contains tests for Arc objects.
"""

import json
from datetime import date

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.schemas.arc import Arc
from mokkari.session import Session


def test_known_arc() -> None:
    """Test for known arcs."""
    arc = Arc(
        id=2,
        name="The Witching Hour",
        desc="A DC Comics crossover event.",
        image="https://static.metron.cloud/media/arc/2018/11/13/witching-hour.jpg",
        modified="2019-06-23T15:13:19.432378-04:00",
        resource_url="https://metron.cloud/arc/witching-hour/",
    )
    assert arc.name == "The Witching Hour"
    assert (
        arc.image.__str__() == "https://static.metron.cloud/media/arc/2018/11/13/witching-hour.jpg"
    )
    assert arc.resource_url.__str__() == "https://metron.cloud/arc/witching-hour/"


def test_arcs_list(talker: Session) -> None:
    """Test for ArcsList."""
    data = {
        "count": 3,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 1,
                "name": "'Til Death Do Us...",
                "modified": "2019-06-23T15:13:19.432378-04:00",
            },
            {
                "id": 2,
                "name": "(She) Drunk History",
                "modified": "2019-06-23T15:13:19.432378-04:00",
            },
            {
                "id": 3,
                "name": "1+2 = Fantastic Three",
                "modified": "2019-06-23T15:13:19.432378-04:00",
            },
        ],
    }
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/arc/", text=json.dumps(data))
        arcs = talker.arcs_list()
    arc_iter = iter(arcs)
    assert next(arc_iter).name == "'Til Death Do Us..."
    assert next(arc_iter).name == "(She) Drunk History"
    assert next(arc_iter).name == "1+2 = Fantastic Three"
    assert len(arcs) == 3
    assert arcs[2].name == "1+2 = Fantastic Three"


def test_arc_issue_list(talker: Session) -> None:
    """Test for getting an issue list for an arc."""
    data = {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 6798,
                "series": {"id": 1, "name": "Batman", "volume": 1, "year_began": 2011},
                "number": "1",
                "issue": "Batman (2011) #1",
                "cover_date": "2011-11-01",
                "cover_hash": "abc123",
                "modified": "2019-06-23T15:13:19.432378-04:00",
            },
            {
                "id": 6799,
                "series": {"id": 1, "name": "Batman", "volume": 1, "year_began": 2011},
                "number": "2",
                "issue": "Batman (2011) #2",
                "cover_date": "2011-12-01",
                "cover_hash": "def456",
                "modified": "2019-06-23T15:13:19.432378-04:00",
            },
        ],
    }
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/arc/177/issue_list/", text=json.dumps(data))
        issues = talker.arc_issues_list(177)
    assert len(issues) == 2
    assert issues[0].id == 6798
    assert issues[0].issue_name == "Batman (2011) #1"
    assert issues[0].cover_date == date(2011, 11, 1)


def test_bad_arc(talker: Session) -> None:
    """Test for bad arc requests."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/arc/-8/",
            text='{"response_code": 404, "detail": "Not found."}',
        )

        with pytest.raises(exceptions.ApiError):
            talker.arc(-8)


def test_bad_arc_validate(talker: Session) -> None:
    """Test data with invalid data."""
    # Change the 'name' field to an int, when it should be a string.
    data = {
        "id": 5,
        "name": 10,
        "desc": "Foo Bar",
        "image": "https://static.metron.cloud/media/arc/2018/11/25/ff-26.jpg",
        "modified": "2019-06-23T15:13:19.432378-04:00",
    }
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/arc/500/",
            text=json.dumps(data),
        )

        with pytest.raises(exceptions.ApiError):
            talker.arc(500)

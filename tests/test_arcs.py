"""
Test Arcs module.

This module contains tests for Arc objects.
"""
import json
from datetime import date, datetime, timedelta, timezone

import pytest
import requests_mock

from mokkari import arc, exceptions
from mokkari.session import Session


def test_known_arc(talker: Session) -> None:
    """Test for known arcs."""
    heroes: arc.ArcSchema = talker.arc(1)
    assert heroes.name == "Heroes In Crisis"
    assert (
        heroes.image
        == "https://static.metron.cloud/media/arc/2018/11/12/heroes-in-crisis.jpeg"
    )
    assert heroes.modified == datetime(
        2019,
        6,
        23,
        15,
        13,
        19,
        456634,
        tzinfo=timezone(timedelta(days=-1, seconds=72000), "-0400"),
    )
    assert heroes.resource_url == "https://metron.cloud/arc/heroes-crisis/"


def test_arcslist(talker: Session) -> None:
    """Test for ArcsList."""
    arcs = talker.arcs_list()
    arc_iter = iter(arcs)
    assert next(arc_iter).name == "'Til Death Do Us..."
    assert next(arc_iter).name == "1+2 = Fantastic Three"
    assert next(arc_iter).name == "1883"
    assert len(arcs) == 873
    assert arcs[2].name == "1883"


def test_arc_issue_list(talker: Session) -> None:
    """Test for getting an issue list for an arc."""
    issues = talker.arc_issues_list(177)
    assert len(issues) == 7
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


def test_bad_response_data() -> None:
    """Test for bad arc response."""
    with pytest.raises(exceptions.ApiError):
        arc.ArcsList({"results": {"name": 1}})


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

"""Test Arcs module.

This module contains tests for Arc objects.
"""

import json
from datetime import date

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.session import Session


def test_known_arc(talker: Session) -> None:
    """Test for known arcs."""
    witching = talker.arc(2)
    assert witching.name == "The Witching Hour"
    assert (
        witching.image.__str__()
        == "https://static.metron.cloud/media/arc/2018/11/13/witching-hour.jpg"
    )
    assert witching.resource_url.__str__() == "https://metron.cloud/arc/witching-hour/"


def test_arcs_list(talker: Session) -> None:
    """Test for ArcsList."""
    arcs = talker.arcs_list()
    arc_iter = iter(arcs)
    assert next(arc_iter).name == "'Til Death Do Us..."
    assert next(arc_iter).name == "(She) Drunk History"
    assert next(arc_iter).name == "1+2 = Fantastic Three"
    assert next(arc_iter).name == "1602"
    assert len(arcs) == 2056
    assert arcs[3].name == "1602"


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

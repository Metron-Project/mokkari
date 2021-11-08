"""
Test Arcs module.

This module contains tests for Arc objects.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
import requests_mock

from mokkari import arc, exceptions


def test_known_arc(talker, arc_resp):
    """Test for known arcs."""
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/arc/1/", text=arc_resp)
        heroes = talker.arc(1)
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


def test_arcslist(talker, arc_list_resp):
    """Test for ArcsList."""
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/arc/?name=crisis", text=arc_list_resp)
        arcs = talker.arcs_list({"name": "crisis"})
    arc_iter = iter(arcs)
    assert next(arc_iter).name == "Countdown to Final Crisis"
    assert next(arc_iter).name == "Crisis on Earth-Prime"
    assert next(arc_iter).name == "Crisis on Infinite Earths"
    assert len(arcs) == 8
    assert arcs[2].name == "Crisis on Infinite Earths"


def test_bad_arc(talker):
    """Test for bad arc requests."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/arc/-8/",
            text='{"response_code": 404, "detail": "Not found."}',
        )

        with pytest.raises(exceptions.ApiError):
            talker.arc(-8)


def test_bad_response_data():
    """Test for bad arc response."""
    with pytest.raises(exceptions.ApiError):
        arc.ArcsList({"results": {"name": 1}})


def test_bad_arc_validate(talker):
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

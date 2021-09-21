"""
Test Arcs module.

This module contains tests for Arc objects.
"""
from datetime import datetime, timedelta, timezone

import pytest
import requests_mock

from mokkari import arcs_list, exceptions


def test_known_arc(talker):
    """Test for known arcs."""
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


def test_arcslist(talker):
    """Test for ArcsList."""
    arcs = talker.arcs_list()
    arc_iter = iter(arcs)
    assert next(arc_iter).name == "2099"
    assert next(arc_iter).name == "52"
    assert next(arc_iter).name == "A Court of Owls"
    assert len(arcs) == 28
    assert arcs[2].name == "A Court of Owls"


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
        arcs_list.ArcsList({"results": {"name": 1}})

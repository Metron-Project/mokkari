"""
Test Teams module.

This module contains tests for Team objects.
"""
from datetime import datetime, timedelta, timezone

import pytest
import requests_mock

from mokkari import exceptions, teams_list


def test_known_team(talker):
    """Test for a known team."""
    inhumans = talker.team(1)
    assert inhumans.name == "Inhumans"
    assert inhumans.image == "https://static.metron.cloud/media/team/2018/11/11/Inhumans.jpg"
    assert inhumans.wikipedia == "Inhumans"
    assert len(inhumans.creators) == 2
    assert inhumans.modified == datetime(
        2019,
        6,
        23,
        15,
        13,
        23,
        975156,
        tzinfo=timezone(timedelta(days=-1, seconds=72000), "-0400"),
    )


def test_teamlist(talker):
    """Test the TeamsList."""
    teams = talker.teams_list()
    team_iter = iter(teams)
    assert next(team_iter).name == "A-Force"
    assert next(team_iter).name == "A.I.M."
    assert next(team_iter).name == "A.R.G.U.S."
    assert len(teams) == 28
    assert teams[2].name == "A.R.G.U.S."


def test_bad_team(talker):
    """Test for a non-existant team."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/team/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.team(-1)


def test_bad_response_data():
    """Test for a bad team response."""
    with pytest.raises(exceptions.ApiError):
        teams_list.TeamsList({"results": {"name": 1}})

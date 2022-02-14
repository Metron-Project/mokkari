"""
Test Teams module.

This module contains tests for Team objects.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
import requests_mock

from mokkari import exceptions, team


def test_known_team(talker):
    """Test for a known team."""
    inhumans = talker.team(1)
    assert inhumans.name == "Inhumans"
    assert inhumans.image == "https://static.metron.cloud/media/team/2018/11/11/Inhumans.jpg"
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
    assert next(team_iter).name == "A-Next"
    assert next(team_iter).name == "A.I.M."
    assert len(teams) == 499
    assert teams[2].name == "A.I.M."


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
        team.TeamsList({"results": {"name": 1}})


def test_bad_team_validate(talker):
    """Test data with invalid data."""
    # Change the 'name' field to an int, when it should be a string.
    data = {
        "id": 150,
        "name": 50,
        "desc": "Foo Bat",
        "image": "https://static.metron.cloud/media/team/2019/06/20/aquamarines.jpg",
        "creators": [],
        "modified": "2019-06-23T15:13:23.927059-04:00",
    }

    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/team/150/",
            text=json.dumps(data),
        )

        with pytest.raises(exceptions.ApiError):
            talker.team(150)

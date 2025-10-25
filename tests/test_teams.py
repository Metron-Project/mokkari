"""Test Teams module.

This module contains tests for Team objects.
"""

import json
from datetime import date

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.session import Session


def test_known_team(talker: Session) -> None:
    """Test for a known team."""
    inhumans = talker.team(1)
    assert inhumans.name == "Inhumans"
    assert (
        inhumans.image.__str__() == "https://static.metron.cloud/media/team/2018/11/11/Inhumans.jpg"
    )
    assert len(inhumans.creators) == 2
    assert any(item.name == "Earth 616" for item in inhumans.universes)
    assert inhumans.resource_url.__str__() == "https://metron.cloud/team/inhumans/"


def test_team_list(talker: Session) -> None:
    """Test the TeamsList."""
    teams = talker.teams_list()
    team_iter = iter(teams)
    assert next(team_iter).name == "13th Floor Witches"
    assert next(team_iter).name == "22 Brides"
    assert next(team_iter).name == "3K X-Men"
    assert len(teams) == 2315
    assert teams[2].name == "3K X-Men"


def test_team_issue_list(talker: Session) -> None:
    """Test for getting an issue list for an arc."""
    issues = talker.team_issues_list(1)
    assert len(issues) == 721
    assert issues[0].id == 258
    assert issues[0].issue_name == "Fantastic Four (1961) #45"
    assert issues[0].cover_date == date(1965, 12, 1)


def test_bad_team(talker: Session) -> None:
    """Test for a non-existent team."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/team/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.team(-1)


def test_bad_team_validate(talker: Session) -> None:
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

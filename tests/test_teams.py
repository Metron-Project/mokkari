"""Test Teams module.

This module contains tests for Team objects.
"""

import json
from datetime import date

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.schemas.team import Team
from mokkari.session import Session


def test_known_team() -> None:
    """Test for a known team."""
    inhumans = Team(
        id=1,
        name="Inhumans",
        desc="A race of superhumans.",
        image="https://static.metron.cloud/media/team/2018/11/11/Inhumans.jpg",
        creators=[
            {"id": 1, "name": "Stan Lee", "modified": "2019-06-23T15:13:19.432378-04:00"},
            {"id": 2, "name": "Jack Kirby", "modified": "2019-06-23T15:13:19.432378-04:00"},
        ],
        universes=[
            {"id": 1, "name": "Earth 616", "modified": "2019-06-23T15:13:19.432378-04:00"},
        ],
        modified="2019-06-23T15:13:19.432378-04:00",
        resource_url="https://metron.cloud/team/inhumans/",
    )
    assert inhumans.name == "Inhumans"
    assert (
        inhumans.image.__str__() == "https://static.metron.cloud/media/team/2018/11/11/Inhumans.jpg"
    )
    assert len(inhumans.creators) == 2
    assert any(item.name == "Earth 616" for item in inhumans.universes)
    assert inhumans.resource_url.__str__() == "https://metron.cloud/team/inhumans/"


def test_team_list(talker: Session) -> None:
    """Test the TeamsList."""
    data = {
        "count": 3,
        "next": None,
        "previous": None,
        "results": [
            {"id": 1, "name": "13th Floor Witches", "modified": "2019-06-23T15:13:19.432378-04:00"},
            {"id": 2, "name": "22 Brides", "modified": "2019-06-23T15:13:19.432378-04:00"},
            {"id": 3, "name": "3K X-Men", "modified": "2019-06-23T15:13:19.432378-04:00"},
        ],
    }
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/team/", text=json.dumps(data))
        teams = talker.teams_list()
    team_iter = iter(teams)
    assert next(team_iter).name == "13th Floor Witches"
    assert next(team_iter).name == "22 Brides"
    assert next(team_iter).name == "3K X-Men"
    assert len(teams) == 3
    assert teams[2].name == "3K X-Men"


def test_team_issue_list(talker: Session) -> None:
    """Test for getting an issue list for a team."""
    data = {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 258,
                "series": {"id": 1, "name": "Fantastic Four", "volume": 1, "year_began": 1961},
                "number": "45",
                "issue": "Fantastic Four (1961) #45",
                "cover_date": "1965-12-01",
                "cover_hash": "abc123",
                "modified": "2019-06-23T15:13:19.432378-04:00",
            },
            {
                "id": 259,
                "series": {"id": 1, "name": "Fantastic Four", "volume": 1, "year_began": 1961},
                "number": "46",
                "issue": "Fantastic Four (1961) #46",
                "cover_date": "1966-01-01",
                "cover_hash": "def456",
                "modified": "2019-06-23T15:13:19.432378-04:00",
            },
        ],
    }
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/team/1/issue_list/", text=json.dumps(data))
        issues = talker.team_issues_list(1)
    assert len(issues) == 2
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

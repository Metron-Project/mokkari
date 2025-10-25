"""Test Characters module.

This module contains tests for Character objects.
"""

import json
from datetime import date

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.schemas.character import Character
from mokkari.session import Session


def test_no_alias(talker: Session) -> None:
    """Test for no alias attribute."""
    character = talker.character(23843)
    assert isinstance(character, Character)
    assert character.name == "4-D Man"
    assert character.alias == []
    assert character.desc == "An alien from the 4th Dimension."
    assert character.creators == []
    assert character.teams == []
    assert character.cv_id == 137999


def test_known_character(talker: Session) -> None:
    """Test for a known character."""
    black_bolt = talker.character(1)
    assert black_bolt.name == "Black Bolt"
    assert (
        black_bolt.image.__str__()
        == "https://static.metron.cloud/media/character/2018/11/11/black-bolt.jpg"
    )
    assert len(black_bolt.creators) == 2
    assert len(black_bolt.teams) == 3
    assert any(item.name == "Earth 616" for item in black_bolt.universes)
    assert black_bolt.resource_url.__str__() == "https://metron.cloud/character/black-bolt/"


def test_character_list(talker: Session) -> None:
    """Test the CharactersList."""
    chars = talker.characters_list({"name": "man"})
    character_iter = iter(chars)
    assert next(character_iter).name == "'Mazing Man"
    assert next(character_iter).name == "3-D Man (Chandler)"
    assert next(character_iter).name == "3-D Man (Garrett)"
    assert len(chars) == 1371
    assert chars[2].name == "3-D Man (Garrett)"


def test_character_issue_list(talker: Session) -> None:
    """Test for getting an issue list for an arc."""
    issues = talker.character_issues_list(1)
    assert len(issues) == 537
    assert issues[0].id == 258
    assert issues[0].issue_name == "Fantastic Four (1961) #45"
    assert issues[0].cover_date == date(1965, 12, 1)


def test_bad_character(talker: Session) -> None:
    """Test for a non-existing character."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/character/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.character(-1)


def test_bad_character_validate(talker: Session) -> None:
    """Test data with invalid data."""
    # Change the 'name' field to an int, when it should be a string.
    data = {
        "id": 150,
        "name": 50,
        "alias": [],
        "desc": "Foo",
        "image": "https://static.metron.cloud/media/character/2018/11/15/moon-knight.jpg",
        "creators": [
            {
                "id": 146,
                "name": "Doug Moench",
                "modified": "2019-06-23T15:13:21.994966-04:00",
            }
        ],
        "teams": [],
        "modified": "2020-07-29T17:48:36.347982-04:00",
    }

    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/character/150/",
            text=json.dumps(data),
        )

        with pytest.raises(exceptions.ApiError):
            talker.character(150)

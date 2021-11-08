"""
Test Characters module.

This module contains tests for Character objects.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
import requests_mock

from mokkari import character, exceptions


def test_known_character(talker, character_resp):
    """Test for a known character."""
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/character/1/", text=character_resp)
        black_bolt = talker.character(1)
    assert black_bolt.name == "Black Bolt"
    assert (
        black_bolt.image
        == "https://static.metron.cloud/media/character/2018/11/11/black-bolt.jpg"
    )
    assert black_bolt.wikipedia == "Black_Bolt"
    assert len(black_bolt.creators) == 2
    assert len(black_bolt.teams) == 3
    assert black_bolt.modified == datetime(
        2021,
        9,
        9,
        15,
        52,
        49,
        90281,
        tzinfo=timezone(timedelta(days=-1, seconds=72000), "-0400"),
    )


def test_characterlist(talker, character_list_resp):
    """Test the CharactersList."""
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/character/?name=superman", text=character_list_resp)
        character = talker.characters_list({"name": "superman"})
    character_iter = iter(character)
    assert next(character_iter).name == "Composite Superman"
    assert next(character_iter).name == "Cyborg Superman"
    assert next(character_iter).name == "Red Son Superman"
    assert len(character) == 7
    assert character[2].name == "Red Son Superman"


def test_bad_character(talker):
    """Test for a non-existing character."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/character/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.character(-1)


def test_bad_response_data(talker):
    """Test for a bad character response."""
    with pytest.raises(exceptions.ApiError):
        character.CharactersList({"results": {"name": 1}})


def test_bad_character_validate(talker):
    """Test data with invalid data."""
    # Change the 'name' field to an int, when it should be a string.
    data = {
        "id": 150,
        "name": 50,
        "alias": [],
        "desc": "Foo",
        "wikipedia": "Moon_Knight",
        "image": "https://static.metron.cloud/media/character/2018/11/15/moon-knight.jpg",
        "creators": [
            {"id": 146, "name": "Doug Moench", "modified": "2019-06-23T15:13:21.994966-04:00"}
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

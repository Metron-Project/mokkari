"""Test Creator module.

This module contains tests for Creator objects.
"""

import json
from datetime import date

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.session import Session


def test_known_creator(talker: Session) -> None:
    """Test for a known creator."""
    jack = talker.creator(3)
    assert jack.name == "Jack Kirby"
    assert jack.birth == date(1917, 8, 28)
    assert jack.death == date(1994, 2, 6)
    assert (
        jack.image.__str__()
        == "https://static.metron.cloud/media/creator/2018/11/11/432124-Jack_Kirby01.jpg"
    )
    assert jack.resource_url.__str__() == "https://metron.cloud/creator/jack-kirby/"


def test_creator_list(talker: Session) -> None:
    """Test the CreatorsList."""
    creators = talker.creators_list({"name": "man"})
    creator_iter = iter(creators)
    assert next(creator_iter).name == "A. J. Lieberman"
    assert next(creator_iter).name == "Aadi Salman"
    assert next(creator_iter).name == "Aaron Guzman"
    assert next(creator_iter).name == "Abel Laxamana"
    assert len(creators) == 543
    assert creators[3].name == "Abel Laxamana"


def test_bad_creator(talker: Session) -> None:
    """Test for a non-existent creator."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/creator/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.creator(-1)


def test_bad_creator_validate(talker: Session) -> None:
    """Test data with invalid data."""
    # Change the 'name' field to an int, when it should be a string.
    data = {
        "id": 150,
        "name": 50,
        "birth": None,
        "death": None,
        "desc": "Foo Bar",
        "image": "https://static.metron.cloud/media/creator/2018/11/13/Jim_Cheung.jpg",
        "modified": "2019-06-23T15:13:22.423371-04:00",
    }

    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/creator/150/",
            text=json.dumps(data),
        )

        with pytest.raises(exceptions.ApiError):
            talker.creator(150)

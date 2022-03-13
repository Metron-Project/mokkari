"""
Test Creator module.

This module contains tests for Creator objects.
"""
import json
from datetime import date, datetime, timedelta, timezone

import pytest
import requests_mock

from mokkari import creator, exceptions


def test_known_creator(talker):
    """Test for a known creator."""
    jack = talker.creator(3)
    assert jack.name == "Jack Kirby"
    assert jack.birth == date(1917, 8, 28)
    assert jack.death == date(1994, 2, 6)
    assert (
        jack.image
        == "https://static.metron.cloud/media/creator/2018/11/11/432124-Jack_Kirby01.jpg"
    )
    assert jack.modified == datetime(
        2019,
        6,
        23,
        15,
        13,
        22,
        311024,
        tzinfo=timezone(timedelta(days=-1, seconds=72000), "-0400"),
    )


def test_comiclist(talker):
    """Test the CreatorsList."""
    creators = talker.creators_list({"name": "man"})
    creator_iter = iter(creators)
    assert next(creator_iter).name == "A. J. Lieberman"
    assert next(creator_iter).name == "Adam Freeman"
    assert next(creator_iter).name == "Adam Schlagman"
    assert next(creator_iter).name == "Al Sulman"
    assert len(creators) == 186
    assert creators[3].name == "Al Sulman"


def test_bad_creator(talker):
    """Test for a non-existant creator."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/creator/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.creator(-1)


def test_bad_response_data(talker):
    """Test for a bad creator response."""
    with pytest.raises(exceptions.ApiError):
        creator.CreatorsList({"results": {"name": 1}})


def test_bad_creator_validate(talker):
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

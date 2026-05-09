"""Test Publishers module.

This module contains tests for Publisher objects.
"""

import json

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.schemas.publisher import Publisher
from mokkari.session import Session


def test_known_publishers() -> None:
    """Test for a known publisher."""
    marvel = Publisher(
        id=1,
        name="Marvel",
        founded=1939,
        country="US",
        desc="Marvel Comics.",
        image="https://static.metron.cloud/media/publisher/2018/11/11/marvel.jpg",
        modified="2019-06-23T15:13:19.432378-04:00",
        resource_url="https://metron.cloud/publisher/marvel/",
    )
    assert marvel.name == "Marvel"
    assert (
        marvel.image.__str__()
        == "https://static.metron.cloud/media/publisher/2018/11/11/marvel.jpg"
    )
    assert marvel.founded == 1939
    assert marvel.country == "US"
    assert marvel.resource_url.__str__() == "https://metron.cloud/publisher/marvel/"


def test_publisher_list(talker: Session) -> None:
    """Test the PublishersList."""
    data = {
        "count": 3,
        "next": None,
        "previous": None,
        "results": [
            {"id": 1, "name": "12-Gauge Comics", "modified": "2019-06-23T15:13:19.432378-04:00"},
            {"id": 2, "name": "AAA Pop Comics", "modified": "2019-06-23T15:13:19.432378-04:00"},
            {"id": 3, "name": "AWA Studios", "modified": "2019-06-23T15:13:19.432378-04:00"},
        ],
    }
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/publisher/", text=json.dumps(data))
        publishers = talker.publishers_list()
    publisher_iter = iter(publishers)
    assert next(publisher_iter).name == "12-Gauge Comics"
    assert next(publisher_iter).name == "AAA Pop Comics"
    assert next(publisher_iter).name == "AWA Studios"
    assert len(publishers) == 3
    assert publishers[2].name == "AWA Studios"


def test_bad_publisher(talker: Session) -> None:
    """Test for a non-existent publisher."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/publisher/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.publisher(-1)


def test_bad_publisher_validate(talker: Session) -> None:
    """Test data with invalid data."""
    # Change the 'name' field to an int, when it should be a string.
    data = {
        "id": 15,
        "name": 150,
        "founded": 1993,
        "desc": "Foo Bar",
        "image": "https://static.metron.cloud/media/publisher/2018/12/02/bongo.png",
        "modified": "2019-06-23T15:13:23.581612-04:00",
    }

    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/publisher/15/",
            text=json.dumps(data),
        )

        with pytest.raises(exceptions.ApiError):
            talker.publisher(15)

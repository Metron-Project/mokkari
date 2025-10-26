"""Test Publishers module.

This module contains tests for Publisher objects.
"""

import json

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.session import Session


def test_known_publishers(talker: Session) -> None:
    """Test for a known publisher."""
    marvel = talker.publisher(1)
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
    publishers = talker.publishers_list()
    publisher_iter = iter(publishers)
    assert next(publisher_iter).name == "12-Gauge Comics"
    assert next(publisher_iter).name == "AAA Pop Comics"
    assert next(publisher_iter).name == "AWA Studios"
    assert len(publishers) == 155
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

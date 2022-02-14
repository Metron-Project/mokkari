"""
Test Publishers module.

This module contains tests for Publisher objects.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
import requests_mock

from mokkari import exceptions, publisher


def test_known_publishers(talker):
    """Test for a known publisher."""
    marvel = talker.publisher(1)
    assert marvel.name == "Marvel"
    assert marvel.image == "https://static.metron.cloud/media/publisher/2018/11/11/marvel.jpg"
    assert marvel.founded == 1939
    assert marvel.modified == datetime(
        2019,
        6,
        23,
        15,
        13,
        23,
        591390,
        tzinfo=timezone(timedelta(days=-1, seconds=72000), "-0400"),
    )


def test_publisherlist(talker):
    """Test the PublishersList."""
    publishers = talker.publishers_list()
    publisher_iter = iter(publishers)
    assert next(publisher_iter).name == "12-Gauge Comics"
    assert next(publisher_iter).name == "AWA Studios"
    assert next(publisher_iter).name == "AfterShock Comics"
    assert len(publishers) == 45
    assert publishers[2].name == "AfterShock Comics"


def test_bad_publisher(talker):
    """Test for a non-existant publisher."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/publisher/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.publisher(-1)


def test_bad_response_data():
    """Test for a bad publisher response."""
    with pytest.raises(exceptions.ApiError):
        publisher.PublishersList({"results": {"name": 1}})


def test_bad_publisher_validate(talker):
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

"""
Test Publishers module.

This module contains tests for Publisher objects.
"""
import pytest
import requests_mock

from mokkari import exceptions, publishers_list


def test_known_publishers(talker):
    """Test for a known publisher."""
    marvel = talker.publisher(1)
    assert marvel.name == "Marvel"
    assert marvel.image == "https://static.metron.cloud/media/publisher/2018/11/11/marvel.jpg"
    assert marvel.wikipedia == "Marvel_Comics"
    assert marvel.founded == 1939


def test_publisherlist(talker):
    """Test the PublishersList."""
    publishers = talker.publishers_list()
    publisher_iter = iter(publishers)
    assert next(publisher_iter).name == "12-Gauge Comics"
    assert next(publisher_iter).name == "AWA Studios"
    assert next(publisher_iter).name == "AfterShock Comics"
    assert len(publishers) == 28
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
        publishers_list.PublishersList({"results": {"name": 1}})

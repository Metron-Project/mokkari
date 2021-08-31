"""
Test Cache module.

This module contains tests for SqliteCache objects.
"""
import json

import pytest
import requests_mock

from mokkari import api, exceptions, sqlite_cache


class NoGet:
    """The NoGet object fakes storing data from the sqlite cache."""

    def store(self, key, value):
        """Save no data."""
        # This method should store key value pair
        return


class NoStore:
    """The NoStore object fakes getting data from the sqlite cache."""

    def get(self, key):
        """Retrieve no data."""
        return None


def test_no_get(dummy_username, dummy_password):
    """Test for retrieving failure."""
    m = api(username=dummy_username, passwd=dummy_password, cache=NoGet())

    with pytest.raises(exceptions.CacheError):
        m.series(5)


def test_no_store(dummy_username, dummy_password):
    """Test for saving data error."""
    m = api(username=dummy_username, passwd=dummy_password, cache=NoStore())

    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/series/5/",
            text='{"response_code": 200}',
        )

        with pytest.raises(exceptions.CacheError):
            m.series(5)


def test_sql_store(dummy_username, dummy_password):
    """Test for saving data to the sqlite cache."""
    fresh_cache = sqlite_cache.SqliteCache(":memory:")
    test_cache = sqlite_cache.SqliteCache("tests/testing_mock.sqlite")

    m = api(username=dummy_username, passwd=dummy_password, cache=fresh_cache)
    url = "https://metron.cloud/api/series/1/"

    assert fresh_cache.get(url) is None

    try:
        with requests_mock.Mocker() as r:
            r.get(url, text=json.dumps(test_cache.get(url)))
            m.series(1)

        assert fresh_cache.get(url) is not None
    except TypeError:
        print(
            "This test will fail after cache db deleted.\n"
            "It should pass if you now re-run the test suite without deleting the database."
        )
        assert False

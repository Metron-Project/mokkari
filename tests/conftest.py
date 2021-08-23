import os

import pytest

from mokkari import api, sqlite_cache


@pytest.fixture(scope="session")
def dummy_username():
    return os.getenv("METRON_USERNAME", "username")


@pytest.fixture(scope="session")
def dummy_password():
    return os.getenv("METRON_PASSWD", "passwd")


@pytest.fixture(scope="session")
def talker(dummy_username, dummy_password):
    return api(
        username=dummy_username,
        passwd=dummy_password,
        cache=sqlite_cache.SqliteCache("tests/testing_mock.sqlite"),
    )

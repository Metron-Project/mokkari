"""
Conftest module.

This module contains pytest fixtures.
"""
import os

import pytest

from mokkari import api, sqlite_cache


@pytest.fixture(scope="session")
def dummy_username():
    """Username fixture."""
    return os.getenv("METRON_USERNAME", "username")


@pytest.fixture(scope="session")
def dummy_password():
    """Password fixture."""
    return os.getenv("METRON_PASSWD", "passwd")


@pytest.fixture(scope="session")
def talker(dummy_username, dummy_password):
    """Mokkari api fixture."""
    return api(
        username=dummy_username,
        passwd=dummy_password,
        cache=sqlite_cache.SqliteCache("tests/testing_mock.sqlite"),
    )

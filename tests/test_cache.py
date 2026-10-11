"""Test Cache module.

This module contains tests for SqliteCache objects.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
import requests_mock

from mokkari import api, exceptions, sqlite_cache
from mokkari.session import Session


class NoGet:
    """The NoGet object fakes storing data from the sqlite cache."""

    def store(
        self: NoGet,
        key: any,  # noqa: ARG002
        value: any,  # noqa: ARG002
        *,
        resource: str | None = None,  # noqa: ARG002
        kind: str | None = None,  # noqa: ARG002
    ) -> None:
        """Save no data."""
        # This method should store key value pair
        return


class NoStore:
    """The NoStore object fakes getting data from the sqlite cache."""

    def get(self: NoStore, key: any) -> None:  # noqa: ARG002
        """Retrieve no data."""
        return


def test_no_get(dummy_api_token: str) -> None:
    """Test for retrieving failure."""
    m = api(api_token=dummy_api_token, cache=NoGet())

    with pytest.raises(exceptions.CacheError):
        m.series(5)


def test_no_store(dummy_api_token: str) -> None:
    """Test for saving data error."""
    m = api(api_token=dummy_api_token, cache=NoStore())

    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/series/5/",
            text='{"response_code": 200}',
        )

        with pytest.raises(exceptions.CacheError):
            m.series(5)


def test_thread_safety() -> None:
    """Concurrent get/store calls from multiple threads should not raise."""
    cache = sqlite_cache.SqliteCache(":memory:")

    def worker(i: int) -> None:
        key = f"key-{i}"
        cache.store(key, {"id": i})
        assert cache.get(key) == {"id": i}

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(worker, range(100)))


def test_expire_is_deprecated() -> None:
    """Passing expire still works, but warns from the caller's code that 5.0 removes it."""
    with pytest.warns(DeprecationWarning, match="default_ttl") as record:
        cache = sqlite_cache.SqliteCache(":memory:", expire=7)

    assert cache.expire == 7
    assert record[0].filename == __file__


def test_sqlite_cache_without_expire_does_not_warn(dummy_api_token: str, recwarn) -> None:
    """A SqliteCache built without expire, and a Session using it, don't warn."""
    api(api_token=dummy_api_token, cache=sqlite_cache.SqliteCache(":memory:"))

    assert not [w for w in recwarn if issubclass(w.category, DeprecationWarning)]


class OldStore:
    """A custom cache with the 4.x store(key, value) signature."""

    def get(self: OldStore, key: str) -> None:  # noqa: ARG002
        """Retrieve no data."""
        return

    def store(self: OldStore, key: str, value: any) -> None:  # noqa: ARG002
        """Save no data."""
        return


class KeywordStore(OldStore):
    """A custom cache whose store() already takes mokkari 5.0's keywords."""

    def store(
        self: KeywordStore,
        key: str,  # noqa: ARG002
        value: any,  # noqa: ARG002
        *,
        resource: str | None = None,  # noqa: ARG002
        kind: str | None = None,  # noqa: ARG002
    ) -> None:
        """Save no data."""
        return


class KwargsStore(OldStore):
    """A custom cache whose store() takes any keywords."""

    def store(self: KwargsStore, key: str, value: any, **kwargs: any) -> None:  # noqa: ARG002
        """Save no data."""
        return


@pytest.mark.parametrize("factory", [api, Session])
def test_old_store_signature_is_deprecated(factory, dummy_api_token: str) -> None:
    """A custom store(key, value) warns from the caller's code, naming the cache class."""
    with pytest.warns(DeprecationWarning, match=r"OldStore\.store\(\)") as record:
        factory(api_token=dummy_api_token, cache=OldStore())

    assert record[0].filename == __file__


@pytest.mark.parametrize("cache", [KeywordStore(), KwargsStore(), NoStore()])
def test_compatible_or_storeless_cache_does_not_warn(cache, dummy_api_token: str, recwarn) -> None:
    """Caches that already take 5.0's keywords, or have no store(), don't warn."""
    api(api_token=dummy_api_token, cache=cache)

    assert not [w for w in recwarn if issubclass(w.category, DeprecationWarning)]


# def test_sql_store(dummy_api_token: str) -> None:
#     """Test for saving data to the sqlite cache."""
#     fresh_cache = sqlite_cache.SqliteCache(":memory:")
#     test_cache = sqlite_cache.SqliteCache("tests/testing_mock.sqlite")

#     m = api(api_token=dummy_api_token, cache=fresh_cache)
#     url = "https://metron.cloud/api/series/1/"

#     assert fresh_cache.get(url) is None

#     try:
#         with requests_mock.Mocker() as r:
#             r.get(url, text=json.dumps(test_cache.get(url)))
#             m.series(1)

#         assert fresh_cache.get(url) is not None
#     except TypeError:
#         print(
#             "This test will fail after cache db deleted.\n"
#             "It should pass if you now re-run the test suite without deleting the database."
#         )
#         assert False

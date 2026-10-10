"""Test Redis Cache module.

This module contains the RedisCache tests that depend on how it uses Redis, run against
fakeredis. Tests that also apply to SqliteCache are in test_cache.py.
"""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Any

import fakeredis
import pytest
import requests_mock

from mokkari import api
from mokkari.cache import NO_CACHE
from mokkari.redis_cache import RedisCache

EMPTY_LIST: dict[str, Any] = {"count": 0, "next": None, "previous": None, "results": []}
FULL_LIST: dict[str, Any] = {"count": 1, "next": None, "previous": None, "results": [{"id": 1}]}

HOUR_MS = 3_600_000


@pytest.fixture
def client() -> fakeredis.FakeRedis:
    """A client for a fake Redis server of the test's own."""
    return fakeredis.FakeRedis(server=fakeredis.FakeServer())


@pytest.fixture
def cache(client: fakeredis.FakeRedis) -> RedisCache:
    """A cache with a one-hour default TTL."""
    return RedisCache(client, default_ttl=timedelta(hours=1))


def assert_pttl(client: fakeredis.FakeRedis, key: str, expected_ms: int) -> None:
    """Assert ``key`` expires in ``expected_ms``, allowing for time passing during the test."""
    assert expected_ms - 1000 < client.pttl(key) <= expected_ms


def test_entry_key_layout(client: fakeredis.FakeRedis, cache: RedisCache) -> None:
    """An entry is stored as JSON under the prefix and format version."""
    cache.store("https://metron.cloud/api/series/1/", {"id": 1}, resource="series", kind="detail")

    assert client.get("mokkari:cache:v1:https://metron.cloud/api/series/1/") == b'{"id": 1}'
    assert client.zrange("mokkari:cache:v1:idx:series:detail", 0, -1) == [
        b"mokkari:cache:v1:https://metron.cloud/api/series/1/"
    ]


def test_entry_expires_with_its_ttl(client: fakeredis.FakeRedis, cache: RedisCache) -> None:
    """An entry is given the TTL its resource and kind resolve to, and Redis expires it."""
    cache.store("key", {"id": 1}, resource="series", kind="detail")

    assert_pttl(client, "mokkari:cache:v1:key", HOUR_MS)
    client.pexpire("mokkari:cache:v1:key", 1)
    time.sleep(0.01)
    assert cache.get("key") is None


def test_sub_millisecond_ttl_still_expires(client: fakeredis.FakeRedis) -> None:
    """A TTL shorter than Redis's resolution is rounded up rather than to "never"."""
    cache = RedisCache(client, default_ttl=timedelta(microseconds=1))
    cache.store("key", {"id": 1}, resource="series", kind="detail")

    # -2 means the entry has already expired, as it can on a slow runner; -1 would mean never.
    assert client.pttl("mokkari:cache:v1:key") in {-2, 0, 1}


def test_none_ttl_never_expires(client: fakeredis.FakeRedis) -> None:
    """A TTL of None stores the entry, and its index set, without an expiry."""
    cache = RedisCache(client, ttl={"role": RedisCache.NEVER})
    cache.store("key", {"id": 1}, resource="role", kind="list")

    assert client.pttl("mokkari:cache:v1:key") == -1
    assert client.pttl("mokkari:cache:v1:idx:role:list") == -1


def test_empty_list_ttl(client: fakeredis.FakeRedis) -> None:
    """An empty list gets the shorter empty_list_ttl."""
    cache = RedisCache(client, default_ttl=timedelta(hours=1), empty_list_ttl=timedelta(minutes=30))
    cache.store("key", EMPTY_LIST, resource="issue", kind="list")

    assert_pttl(client, "mokkari:cache:v1:key", HOUR_MS // 2)


def test_no_cache_writes_nothing(client: fakeredis.FakeRedis) -> None:
    """A NO_CACHE resource leaves no entry or index set behind."""
    cache = RedisCache(client, ttl={"issue": NO_CACHE})
    cache.store("key", {"id": 1}, resource="issue", kind="detail")

    assert client.keys() == []


def test_index_set_outlives_its_entries(client: fakeredis.FakeRedis) -> None:
    """An index set expires with its longest-lived entry."""
    cache = RedisCache(client, default_ttl=timedelta(hours=1), empty_list_ttl=timedelta(minutes=30))
    index = "mokkari:cache:v1:idx:issue:list"

    cache.store("empty1", EMPTY_LIST, resource="issue", kind="list")
    assert_pttl(client, index, HOUR_MS // 2)
    cache.store("full", FULL_LIST, resource="issue", kind="list")
    assert_pttl(client, index, HOUR_MS)
    cache.store("empty2", EMPTY_LIST, resource="issue", kind="list")
    assert_pttl(client, index, HOUR_MS)


def test_index_set_follows_replaced_entry(client: fakeredis.FakeRedis) -> None:
    """Re-storing an entry with a shorter TTL shortens the index set's expiry to match."""
    cache = RedisCache(client, default_ttl=timedelta(hours=1), empty_list_ttl=timedelta(minutes=30))
    index = "mokkari:cache:v1:idx:issue:list"

    cache.store("key", FULL_LIST, resource="issue", kind="list")
    cache.store("key", EMPTY_LIST, resource="issue", kind="list")
    assert_pttl(client, index, HOUR_MS // 2)


def test_store_prunes_expired_members(client: fakeredis.FakeRedis, cache: RedisCache) -> None:
    """Keys whose entries have expired are dropped from the index set on the next store."""
    index = "mokkari:cache:v1:idx:series:detail"
    cache.store("old", 1, resource="series", kind="detail")
    # Backdate the member's expiry, as if its entry had expired an hour ago.
    client.zadd(index, {"mokkari:cache:v1:old": 0})
    client.delete("mokkari:cache:v1:old")

    cache.store("new", 2, resource="series", kind="detail")
    assert client.zrange(index, 0, -1) == [b"mokkari:cache:v1:new"]


def test_never_expiring_entry_keeps_index_set(client: fakeredis.FakeRedis) -> None:
    """Once an index set holds an entry that never expires, it doesn't expire either."""
    index = "mokkari:cache:v1:idx:role:list"
    RedisCache(client, ttl={"role": None}).store("forever", 1, resource="role", kind="list")
    RedisCache(client, default_ttl=timedelta(hours=1)).store(
        "timed", 2, resource="role", kind="list"
    )

    assert client.pttl(index) == -1
    # An index set that expired, or was invalidated, with the entry still there is created anew.
    client.delete(index)
    RedisCache(client, ttl={"role": None}).store("forever", 1, resource="role", kind="list")
    assert client.pttl(index) == -1


def test_invalidate_removes_index_sets(client: fakeredis.FakeRedis, cache: RedisCache) -> None:
    """invalidate() removes the resource's index sets along with its entries."""
    cache.store("s1", 1, resource="series", kind="detail")
    cache.store("s2", 2, resource="series", kind="list")
    cache.store("i1", 3, resource="issue", kind="detail")

    assert cache.invalidate("series") == 2
    assert sorted(client.keys()) == [b"mokkari:cache:v1:i1", b"mokkari:cache:v1:idx:issue:detail"]


def test_invalidate_skips_expired_members(client: fakeredis.FakeRedis, cache: RedisCache) -> None:
    """A key in an index set whose entry has already gone isn't counted as removed."""
    cache.store("s1", 1, resource="series", kind="detail")
    cache.store("s2", 2, resource="series", kind="detail")
    client.delete("mokkari:cache:v1:s1")

    assert cache.invalidate("series") == 1
    assert client.keys() == []


def test_invalidate_unknown_resource(cache: RedisCache) -> None:
    """Invalidating a resource with nothing cached removes nothing."""
    assert cache.invalidate("series") == 0


def test_invalidate_many_entries(client: fakeredis.FakeRedis, cache: RedisCache) -> None:
    """invalidate() removes more entries than fit in one batch."""
    for i in range(1200):
        cache.store(f"key-{i}", i, resource="series", kind="detail")

    assert cache.invalidate("series") == 1200
    assert client.keys() == []


def test_clear_leaves_other_keys(client: fakeredis.FakeRedis, cache: RedisCache) -> None:
    """clear() counts and removes only this cache's entries and index sets."""
    client.set("other", "x")
    client.set("mokkari:ratelimit:{user}:daily", "x")
    for i in range(1200):
        cache.store(f"key-{i}", i, resource="series", kind="detail")

    assert cache.clear() == 1200
    assert sorted(client.keys()) == [b"mokkari:ratelimit:{user}:daily", b"other"]


def test_clear_escapes_glob_characters(client: fakeredis.FakeRedis) -> None:
    """A key_prefix with glob characters doesn't match other prefixes in clear()."""
    star = RedisCache(client, key_prefix="app*")
    other = RedisCache(client, key_prefix="apple")
    star.store("key", 1, resource="series", kind="detail")
    other.store("key", 2, resource="series", kind="detail")

    assert star.clear() == 1
    assert other.get("key") == 2


def test_key_prefixes_are_separate(client: fakeredis.FakeRedis) -> None:
    """Caches with different key_prefix values don't see or remove each other's entries."""
    one = RedisCache(client, key_prefix="one")
    two = RedisCache(client, key_prefix="two")
    one.store("key", 1, resource="series", kind="detail")
    two.store("key", 2, resource="series", kind="detail")

    assert one.get("key") == 1
    assert one.invalidate("series") == 1
    assert two.get("key") == 2


def test_shared_between_clients() -> None:
    """Caches on separate clients of one Redis server share entries, as across processes."""
    server = fakeredis.FakeServer()
    one = RedisCache(fakeredis.FakeRedis(server=server))
    two = RedisCache(fakeredis.FakeRedis(server=server))
    one.store("key", 1, resource="series", kind="detail")

    assert two.get("key") == 1
    assert two.invalidate("series") == 1
    assert one.get("key") is None


def test_decoded_responses() -> None:
    """A client that decodes responses to strings works the same way."""
    client = fakeredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)
    cache = RedisCache(client)
    cache.store("key", {"id": 1}, resource="series", kind="detail")

    assert cache.get("key") == {"id": 1}
    assert cache.invalidate("series") == 1
    cache.store("key", {"id": 1}, resource="series", kind="detail")
    assert cache.clear() == 1
    assert client.keys() == []


def test_session_serves_repeat_from_cache(dummy_api_token: str, cache: RedisCache) -> None:
    """A repeated read is served from Redis without another request."""
    m = api(dummy_api_token, cache=cache)
    url = "https://metron.cloud/api/role/"
    body = {"count": 1, "next": None, "previous": None, "results": [{"id": 1, "name": "Writer"}]}

    with requests_mock.Mocker() as r:
        r.get(url, json=body)
        assert m.role_list()[0].name == "Writer"
        assert m.role_list()[0].name == "Writer"
        assert r.call_count == 1

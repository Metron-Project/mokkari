"""Test Cache module.

This module contains tests for SqliteCache objects.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
import requests_mock

from mokkari import api, exceptions, session, sqlite_cache
from mokkari.cache import NO_CACHE, RESOURCES, CacheKind, Ttl, TtlPolicy
from mokkari.schemas.universe import UniversePost
from mokkari.schemas.wish_list import AcquireWishListItem

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path


class NoGet:
    """The NoGet object fakes storing data from the sqlite cache."""

    def store(self: NoGet, key: Any, value: Any, *, resource: str, kind: str) -> None:  # noqa: ARG002
        """Save no data."""
        return


class NoStore:
    """The NoStore object fakes getting data from the sqlite cache."""

    def get(self: NoStore, key: Any) -> None:  # noqa: ARG002
        """Retrieve no data."""
        return


class FakeClock:
    """Stands in for the ``time`` module so tests can move time forward."""

    def __init__(self) -> None:
        """Start the clock at an arbitrary fixed time."""
        self.now = 1_000_000.0

    def time(self) -> float:
        """Return the fake current time."""
        return self.now

    @staticmethod
    def monotonic() -> float:
        """Return the real monotonic clock, which only times retries."""
        return time.monotonic()

    @staticmethod
    def sleep(seconds: float) -> None:
        """Sleep for real."""
        time.sleep(seconds)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    """Replace the clock SqliteCache reads with one the test controls."""
    fake = FakeClock()
    monkeypatch.setattr(sqlite_cache, "time", fake)
    return fake


@pytest.fixture
def make_cache() -> Iterator[Callable[..., sqlite_cache.SqliteCache]]:
    """Build in-memory caches (by default), closing them all after the test."""
    caches: list[sqlite_cache.SqliteCache] = []

    def factory(db_name: str | Path = ":memory:", **kwargs: Any) -> sqlite_cache.SqliteCache:
        caches.append(sqlite_cache.SqliteCache(db_name, **kwargs))
        return caches[-1]

    yield factory
    for c in caches:
        c.close()


@pytest.fixture
def cache(make_cache: Callable[..., sqlite_cache.SqliteCache]) -> sqlite_cache.SqliteCache:
    """An in-memory cache with a one-hour default TTL."""
    return make_cache(default_ttl=timedelta(hours=1))


def count_rows(cache: sqlite_cache.SqliteCache) -> int:
    """Return the number of rows in the cache table, expired or not."""
    return cache.con.execute("SELECT COUNT(*) FROM cache").fetchone()[0]


# ============================================================================
# Custom cache objects
# ============================================================================


@pytest.mark.parametrize("bad_cache", [NoGet(), NoStore(), object()])
def test_cache_missing_methods_rejected(dummy_api_token: str, bad_cache: object) -> None:
    """A cache without get() and store() is rejected when the session is built."""
    with pytest.raises(exceptions.CacheError, match=r"get\(\) and store\(\)"):
        api(dummy_api_token, cache=bad_cache)  # type: ignore[arg-type]


class OldStoreCache(NoStore):
    """A 4.x-style cache whose store() doesn't take resource and kind."""

    def store(self: OldStoreCache, key: Any, value: Any) -> None:  # noqa: ARG002
        """Save no data."""
        return


class NoKeyGetCache(NoGet):
    """A cache whose get() takes no key."""

    def get(self: NoKeyGetCache) -> None:
        """Retrieve no data."""
        return


class NonCallableGetCache(NoGet):
    """A cache whose get is an attribute rather than a method."""

    get = 1


@pytest.mark.parametrize(
    ("bad_cache", "match"),
    [
        (
            OldStoreCache(),
            r"store\(key, value, \*, resource, kind\) method, not store\(key: 'Any', value: 'Any'\)",
        ),
        (NoKeyGetCache(), r"get\(key\) method, not get\(\)"),
        (NonCallableGetCache(), r"get must be a method"),
    ],
)
def test_cache_wrong_signature_rejected(
    dummy_api_token: str, bad_cache: object, match: str
) -> None:
    """A cache whose methods can't take Session's arguments is rejected when the session is built."""
    with pytest.raises(exceptions.CacheError, match=match):
        api(dummy_api_token, cache=bad_cache)  # type: ignore[arg-type]


def test_cache_with_flexible_signature_accepted(dummy_api_token: str) -> None:
    """A store() taking **kwargs accepts resource and kind, so it passes the check."""

    class KwargsCache(NoStore):
        def store(self, key: Any, value: Any, **kwargs: Any) -> None:  # noqa: ARG002
            return

    assert api(dummy_api_token, cache=KwargsCache()).cache is not None  # type: ignore[arg-type]


def test_custom_cache_accepted(dummy_api_token: str) -> None:
    """Any object with get() and store() methods is accepted, not just SqliteCache."""

    class DictCache:
        def __init__(self) -> None:
            self.data: dict[str, Any] = {}

        def get(self, key: str) -> Any | None:
            return self.data.get(key)

        def store(self, key: str, value: Any, *, resource: str, kind: str) -> None:  # noqa: ARG002
            self.data[key] = value

    cache = DictCache()
    m = api(dummy_api_token, cache=cache)  # type: ignore[arg-type]

    with requests_mock.Mocker() as r:
        r.get(ROLE_PAGE1, json=role_page(None, "Writer"))
        m.role_list({"name": "writer"})
        m.role_list({"name": "writer"})
        assert r.call_count == 1
    assert list(cache.data) == [ROLE_PAGE1]


# ============================================================================
# Storing and reading
# ============================================================================


def test_get_missing_key(cache: sqlite_cache.SqliteCache) -> None:
    """An unknown key returns None."""
    assert cache.get("missing") is None


def test_store_and_get(cache: sqlite_cache.SqliteCache) -> None:
    """Stored data comes back unchanged."""
    cache.store("key", {"id": 1, "names": ["a", "b"]}, resource="series", kind="detail")
    assert cache.get("key") == {"id": 1, "names": ["a", "b"]}


def test_store_upserts(cache: sqlite_cache.SqliteCache) -> None:
    """Storing a key twice replaces the first value instead of adding a second row."""
    cache.store("key", {"v": 1}, resource="series", kind="detail")
    cache.store("key", {"v": 2}, resource="series", kind="detail")

    assert cache.get("key") == {"v": 2}
    assert count_rows(cache) == 1


def test_upsert_refreshes_expiry(clock: FakeClock, cache: sqlite_cache.SqliteCache) -> None:
    """Storing a key again restarts its lifetime."""
    cache.store("key", {"v": 1}, resource="series", kind="detail")
    clock.now += 3000
    cache.store("key", {"v": 2}, resource="series", kind="detail")
    clock.now += 3000

    assert cache.get("key") == {"v": 2}


def test_thread_safety(make_cache: Callable[..., sqlite_cache.SqliteCache]) -> None:
    """Concurrent get/store calls from multiple threads should not raise."""
    cache = make_cache()

    def worker(i: int) -> None:
        key = f"key-{i}"
        cache.store(key, {"id": i}, resource="series", kind="detail")
        assert cache.get(key) == {"id": i}

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(worker, range(100)))


# ============================================================================
# Expiry and TTL resolution
# ============================================================================


def test_get_skips_expired(clock: FakeClock, cache: sqlite_cache.SqliteCache) -> None:
    """An entry is served until its TTL passes, then treated as missing."""
    cache.store("key", {"id": 1}, resource="series", kind="detail")

    clock.now += 3599
    assert cache.get("key") == {"id": 1}
    clock.now += 1
    assert cache.get("key") is None


def test_none_ttl_never_expires(
    clock: FakeClock, make_cache: Callable[..., sqlite_cache.SqliteCache]
) -> None:
    """A TTL of None keeps the entry forever."""
    cache = make_cache(ttl={"role": None})
    cache.store("key", {"id": 1}, resource="role", kind="list")

    clock.now += 10 * 365 * 86400
    assert cache.get("key") == {"id": 1}
    assert cache.con.execute("SELECT expires_at FROM cache").fetchone()[0] is None


def test_none_default_ttl_never_expires(
    clock: FakeClock, make_cache: Callable[..., sqlite_cache.SqliteCache]
) -> None:
    """A default_ttl of None keeps resources without their own TTL forever."""
    cache = make_cache(default_ttl=None)
    cache.store("key", {"id": 1}, resource="series", kind="detail")

    clock.now += 10 * 365 * 86400
    assert cache.get("key") == {"id": 1}


def test_no_cache_ttl_is_not_stored(make_cache: Callable[..., sqlite_cache.SqliteCache]) -> None:
    """A TTL of NO_CACHE means the resource isn't cached at all."""
    cache = make_cache(ttl={"issue": NO_CACHE})
    cache.store("key", {"id": 1}, resource="issue", kind="detail")

    assert cache.get("key") is None
    assert count_rows(cache) == 0


@pytest.mark.parametrize(
    ("resource", "kind", "expected"),
    [
        ("issue", "list", timedelta(hours=6)),
        ("issue", "detail", timedelta(days=2)),
        ("series", "list", timedelta(days=3)),
        ("series", "detail", timedelta(days=7)),
        ("role", "list", None),
    ],
)
def test_ttl_resolution_order(
    resource: str,
    kind: str,
    expected: timedelta | None,
    make_cache: Callable[..., sqlite_cache.SqliteCache],
) -> None:
    """A TTL is looked up by resource:kind, then resource, then default_ttl."""
    cache = make_cache(
        default_ttl=timedelta(days=7),
        ttl={
            "issue:list": timedelta(hours=6),
            "issue": timedelta(days=2),
            "series:list": timedelta(days=3),
            "role": None,
        },
    )
    assert cache.ttl_for(resource, kind) == expected


@pytest.mark.parametrize(
    ("resource", "kind", "expected"),
    [
        ("series", "list", timedelta(hours=6)),
        ("series", "detail", timedelta(days=7)),
        ("issue", "list", timedelta(days=2)),
        ("role", "detail", timedelta(days=30)),
        ("collection", "list", NO_CACHE),
    ],
)
def test_kind_wildcard(
    resource: str,
    kind: CacheKind,
    expected: Ttl,
    make_cache: Callable[..., sqlite_cache.SqliteCache],
) -> None:
    """A "*:kind" entry covers every resource without a TTL of its own."""
    cache = make_cache(
        default_ttl=timedelta(days=7),
        ttl={
            "*:list": timedelta(hours=6),
            "*:detail": timedelta(days=7),
            "issue": timedelta(days=2),
            "role:detail": timedelta(days=30),
        },
    )
    assert cache.ttl_for(resource, kind) == expected


EMPTY_LIST: dict[str, Any] = {"count": 0, "next": None, "previous": None, "results": []}


def test_empty_list_not_cached_by_default(cache: sqlite_cache.SqliteCache) -> None:
    """A list response with no results isn't cached unless empty_list_ttl allows it."""
    cache.store("empty", EMPTY_LIST, resource="issue", kind="list")
    cache.store("full", {"count": 1, "results": [{"id": 1}]}, resource="issue", kind="list")

    assert cache.get("empty") is None
    assert cache.get("full") is not None


def test_empty_list_ttl_shortens(
    clock: FakeClock, make_cache: Callable[..., sqlite_cache.SqliteCache]
) -> None:
    """An empty list expires after empty_list_ttl when that's shorter than its TTL."""
    cache = make_cache(default_ttl=timedelta(hours=1), empty_list_ttl=timedelta(minutes=30))
    cache.store("key", EMPTY_LIST, resource="issue", kind="list")

    clock.now += 1799
    assert cache.get("key") == EMPTY_LIST
    clock.now += 1
    assert cache.get("key") is None


@pytest.mark.parametrize("empty_list_ttl", [timedelta(days=1), None])
def test_empty_list_ttl_never_lengthens(
    empty_list_ttl: Ttl,
    clock: FakeClock,
    make_cache: Callable[..., sqlite_cache.SqliteCache],
) -> None:
    """An empty_list_ttl longer than the usual TTL, or None, leaves the usual TTL in place."""
    cache = make_cache(default_ttl=timedelta(hours=1), empty_list_ttl=empty_list_ttl)
    cache.store("key", EMPTY_LIST, resource="issue", kind="list")

    clock.now += 3599
    assert cache.get("key") == EMPTY_LIST
    clock.now += 1
    assert cache.get("key") is None


def test_empty_list_ttl_keeps_no_cache(make_cache: Callable[..., sqlite_cache.SqliteCache]) -> None:
    """empty_list_ttl can't opt an excluded resource back into the cache."""
    cache = make_cache(empty_list_ttl=None)
    cache.store("key", EMPTY_LIST, resource="collection", kind="list")

    assert cache.get("key") is None


def test_empty_list_ttl_only_for_lists(cache: sqlite_cache.SqliteCache) -> None:
    """A detail response that happens to have a zero count is cached as usual."""
    cache.store("key", {"id": 1, "count": 0}, resource="series", kind="detail")

    assert cache.get("key") == {"id": 1, "count": 0}


@pytest.mark.parametrize(
    ("value", "kind", "expected"),
    [
        (EMPTY_LIST, "list", timedelta(minutes=30)),
        ({"count": 1, "results": [{"id": 1}]}, "list", timedelta(hours=1)),
        ({"id": 1, "count": 0}, "detail", timedelta(hours=1)),
    ],
)
def test_ttl_policy_ttl_for_value(value: Any, kind: CacheKind, expected: Ttl) -> None:
    """TtlPolicy applies empty_list_ttl on its own, for backends other than SqliteCache."""
    policy = TtlPolicy(default_ttl=timedelta(hours=1), empty_list_ttl=timedelta(minutes=30))

    assert policy.ttl_for_value(value, resource="issue", kind=kind) == expected


def test_ttl_policy_checks_ttls() -> None:
    """TtlPolicy rejects bad TTLs and keys itself, not only through SqliteCache."""
    with pytest.raises(ValueError, match="must be positive"):
        TtlPolicy(default_ttl=timedelta(0))
    with pytest.raises(ValueError, match="unknown resource"):
        TtlPolicy(ttl={"issues": timedelta(hours=1)})


@pytest.mark.parametrize("resource", ["collection", "pull_list", "wish_list"])
def test_user_data_not_cached_by_default(cache: sqlite_cache.SqliteCache, resource: str) -> None:
    """Per-user resources aren't cached unless the caller opts in."""
    cache.store("key", {"id": 1}, resource=resource, kind="list")
    assert cache.get("key") is None


def test_user_data_opt_in(make_cache: Callable[..., sqlite_cache.SqliteCache]) -> None:
    """A user-supplied TTL overrides the built-in exclusion."""
    cache = make_cache(ttl={"collection": timedelta(minutes=10)}, empty_list_ttl=None)
    cache.store("key", {"id": 1}, resource="collection", kind="list")

    assert cache.get("key") == {"id": 1}
    # The other defaults still apply.
    assert cache.ttl_for("pull_list", "list") is NO_CACHE


def test_user_data_opt_in_by_kind(make_cache: Callable[..., sqlite_cache.SqliteCache]) -> None:
    """A resource:kind entry overrides a built-in resource-level exclusion."""
    cache = make_cache(ttl={"wish_list:list": timedelta(minutes=5)})

    assert cache.ttl_for("wish_list", "list") == timedelta(minutes=5)
    assert cache.ttl_for("wish_list", "detail") is NO_CACHE


def test_class_sentinels(make_cache: Callable[..., sqlite_cache.SqliteCache]) -> None:
    """SqliteCache.NEVER and SqliteCache.NO_CACHE mean the same as None and NO_CACHE."""
    cache = make_cache(
        ttl={"role": sqlite_cache.SqliteCache.NEVER, "issue": sqlite_cache.SqliteCache.NO_CACHE}
    )

    assert cache.ttl_for("role", "list") is None
    assert cache.ttl_for("issue", "detail") is NO_CACHE


@pytest.mark.parametrize(
    "kwargs",
    [
        {"default_ttl": timedelta(seconds=-1)},
        {"ttl": {"issue": timedelta(seconds=-1)}},
        # 4.x used expire=0 for "never expire", so zero is rejected rather than read as anything.
        {"default_ttl": timedelta(0)},
        {"ttl": {"issue": timedelta(0)}},
        {"empty_list_ttl": timedelta(0)},
    ],
)
def test_non_positive_ttl_rejected(kwargs: dict[str, Any]) -> None:
    """A zero or negative TTL is rejected up front, pointing at NO_CACHE and None."""
    with pytest.raises(ValueError, match=r"must be positive.*NO_CACHE"):
        sqlite_cache.SqliteCache(":memory:", **kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"default_ttl": 7},
        {"ttl": {"issue": 0}},
        {"ttl": {"issue": 3600.0}},
    ],
)
def test_non_timedelta_ttl_rejected(kwargs: dict[str, Any]) -> None:
    """A bare number, like a 4.x expire value in days, is rejected rather than guessed at."""
    with pytest.raises(TypeError, match="must be a timedelta, None or NO_CACHE"):
        sqlite_cache.SqliteCache(":memory:", **kwargs)


@pytest.mark.parametrize(
    ("key", "match"),
    [
        ("issues", r"unknown resource 'issues'"),
        ("issues:list", r"unknown resource 'issues'"),
        ("collection:lists", r"unknown kind 'lists'"),
        ("issue:", r"unknown kind ''"),
        ("*:details", r"unknown kind 'details'"),
        ("*", r"needs a kind.*default_ttl"),
        ("issue:list:extra", r"unknown kind 'list:extra'"),
    ],
)
def test_unknown_ttl_key_rejected(key: str, match: str) -> None:
    """A ttl key that could never match, such as a typo, is rejected rather than ignored."""
    with pytest.raises(ValueError, match=match):
        sqlite_cache.SqliteCache(":memory:", ttl={key: timedelta(hours=1)})


def test_every_ttl_key_form_accepted() -> None:
    """Each resource can be given alone or with either kind, and either kind with '*'."""
    keys = [
        *RESOURCES,
        *(f"{resource}:{kind}" for resource in RESOURCES for kind in ("detail", "list")),
        "*:detail",
        "*:list",
    ]
    with sqlite_cache.SqliteCache(":memory:", ttl=dict.fromkeys(keys, timedelta(hours=1))) as cache:
        assert cache.ttl_for("role", "list") == timedelta(hours=1)


def test_resources_match_session_endpoints() -> None:
    """Every resource Session caches under can be given a TTL."""
    endpoints = {value for name, value in vars(session.ResourceEndpoint).items() if name.isupper()}
    assert endpoints | {"role", "series_type"} == RESOURCES


# ============================================================================
# Management
# ============================================================================


def test_delete(cache: sqlite_cache.SqliteCache) -> None:
    """delete() removes one key and reports whether it existed."""
    cache.store("a", 1, resource="series", kind="detail")
    cache.store("b", 2, resource="series", kind="detail")

    assert cache.delete("a") is True
    assert cache.delete("a") is False
    assert cache.get("a") is None
    assert cache.get("b") == 2


def test_invalidate_resource(cache: sqlite_cache.SqliteCache) -> None:
    """invalidate(resource) removes every kind of entry for that resource only."""
    cache.store("s1", 1, resource="series", kind="detail")
    cache.store("s2", 2, resource="series", kind="list")
    cache.store("i1", 3, resource="issue", kind="detail")

    assert cache.invalidate("series") == 2
    assert cache.get("s1") is None
    assert cache.get("s2") is None
    assert cache.get("i1") == 3


def test_invalidate_resource_kind(cache: sqlite_cache.SqliteCache) -> None:
    """invalidate(resource, kind) leaves the resource's other kind alone."""
    cache.store("s1", 1, resource="series", kind="detail")
    cache.store("s2", 2, resource="series", kind="list")

    assert cache.invalidate("series", "list") == 1
    assert cache.get("s1") == 1
    assert cache.get("s2") is None


def test_clear(cache: sqlite_cache.SqliteCache) -> None:
    """clear() removes everything."""
    cache.store("a", 1, resource="series", kind="detail")
    cache.store("b", 2, resource="issue", kind="list")

    assert cache.clear() == 2
    assert count_rows(cache) == 0


def test_cleanup(clock: FakeClock, make_cache: Callable[..., sqlite_cache.SqliteCache]) -> None:
    """cleanup() deletes only expired rows."""
    cache = make_cache(default_ttl=timedelta(hours=1), ttl={"role": None})
    cache.store("short", 1, resource="series", kind="detail")
    cache.store("forever", 2, resource="role", kind="list")
    clock.now += 3600

    assert cache.cleanup() == 1
    assert count_rows(cache) == 1
    assert cache.get("forever") == 2


def test_open_purges_expired(clock: FakeClock, tmp_path: Path) -> None:
    """Opening a cache cleans up rows that expired since it was last used."""
    db = tmp_path / "cache.db"
    with sqlite_cache.SqliteCache(db, default_ttl=timedelta(hours=1)) as cache:
        cache.store("key", 1, resource="series", kind="detail")
    clock.now += 3600

    with sqlite_cache.SqliteCache(db) as cache:
        assert count_rows(cache) == 0


def test_close_and_context_manager(tmp_path: Path) -> None:
    """The context manager closes the connection, and closing twice is harmless."""
    with sqlite_cache.SqliteCache(tmp_path / "cache.db") as cache:
        cache.store("key", 1, resource="series", kind="detail")
        con = cache.con

    cache.close()
    with pytest.raises(sqlite3.ProgrammingError):
        con.execute("SELECT 1")


def test_reopens_after_close(tmp_path: Path) -> None:
    """A closed cache reopens on the next call, keeping a file-backed cache's entries."""
    cache = sqlite_cache.SqliteCache(tmp_path / "cache.db")
    cache.store("a", 1, resource="series", kind="detail")
    cache.close()

    assert cache.get("a") == 1
    cache.close()
    cache.store("b", 2, resource="series", kind="detail")
    cache.close()
    assert cache.delete("a")
    assert cache.journal_mode == "wal"
    cache.close()


def test_in_memory_reopens_empty() -> None:
    """A closed in-memory cache reopens as a fresh, working database."""
    cache = sqlite_cache.SqliteCache(":memory:")
    cache.store("key", 1, resource="series", kind="detail")
    cache.close()

    assert cache.get("key") is None
    cache.store("key", 2, resource="series", kind="detail")
    assert cache.get("key") == 2
    cache.close()


def test_reopen_purges_expired(clock: FakeClock, tmp_path: Path) -> None:
    """Reopening a closed cache purges entries that expired while it was closed."""
    cache = sqlite_cache.SqliteCache(tmp_path / "cache.db", default_ttl=timedelta(hours=1))
    cache.store("key", 1, resource="series", kind="detail")
    cache.close()
    clock.now += 3600

    assert count_rows(cache) == 0
    cache.close()


def test_close_while_in_use(tmp_path: Path) -> None:
    """Closing from one thread while others use the cache never breaks their calls."""
    cache = sqlite_cache.SqliteCache(tmp_path / "cache.db")

    def worker(i: int) -> None:
        for j in range(50):
            cache.store(f"{i}-{j}", j, resource="series", kind="detail")
            assert cache.get(f"{i}-{j}") == j
            if j % 10 == 0:
                cache.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(worker, range(4)))
    cache.close()


# ============================================================================
# Schema
# ============================================================================


def test_persists_across_connections(tmp_path: Path) -> None:
    """Entries in a file-backed cache survive reopening it."""
    db = tmp_path / "cache.db"
    with sqlite_cache.SqliteCache(db) as cache:
        cache.store("key", {"id": 1}, resource="series", kind="detail")

    with sqlite_cache.SqliteCache(db) as cache:
        assert cache.get("key") == {"id": 1}


def test_file_backed_uses_wal(tmp_path: Path) -> None:
    """A file-backed cache uses WAL mode and records its schema version."""
    with sqlite_cache.SqliteCache(tmp_path / "cache.db") as cache:
        assert cache.journal_mode == "wal"
        assert cache.con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert cache.con.execute("PRAGMA user_version").fetchone()[0] == sqlite_cache.SCHEMA_VERSION


def test_in_memory_stays_in_memory_mode(caplog: pytest.LogCaptureFixture) -> None:
    """An in-memory cache can't use WAL, which is expected and not worth a warning."""
    with caplog.at_level(logging.WARNING), sqlite_cache.SqliteCache(":memory:") as cache:
        assert cache.journal_mode == "memory"
    assert not caplog.records


def test_busy_timeout_is_set(tmp_path: Path) -> None:
    """The connection waits for other processes' locks instead of failing right away."""
    with sqlite_cache.SqliteCache(tmp_path / "cache.db") as cache:
        assert cache.con.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


class WalRefusedConnection(sqlite3.Connection):
    """A connection where WAL can't be enabled, as on a network filesystem."""

    def execute(self, sql: str, *args: Any) -> sqlite3.Cursor:
        """Leave the journal mode unchanged when asked for WAL, as SQLite does."""
        if sql == "PRAGMA journal_mode=WAL":
            sql = "PRAGMA journal_mode"
        return super().execute(sql, *args)


class WalErrorConnection(sqlite3.Connection):
    """A connection where asking for WAL raises, e.g. while another process holds a lock."""

    def execute(self, sql: str, *args: Any) -> sqlite3.Cursor:
        """Raise when asked for WAL."""
        if sql == "PRAGMA journal_mode=WAL":
            msg = "database is locked"
            raise sqlite3.OperationalError(msg)
        return super().execute(sql, *args)


@pytest.mark.parametrize("factory", [WalRefusedConnection, WalErrorConnection])
def test_falls_back_without_wal(
    factory: type[sqlite3.Connection],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When WAL isn't available the cache warns and keeps working in the default mode."""
    connect = sqlite3.connect
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: connect(*a, factory=factory, **kw))
    # Don't spend the full busy timeout retrying a lock that never clears.
    monkeypatch.setattr(sqlite_cache, "_BUSY_TIMEOUT", 0.05)

    with caplog.at_level(logging.WARNING), sqlite_cache.SqliteCache(tmp_path / "cache.db") as cache:
        assert cache.journal_mode == "delete"
        cache.store("key", {"id": 1}, resource="series", kind="detail")
        assert cache.get("key") == {"id": 1}
    assert "Couldn't enable WAL" in caplog.text


class WalBriefLockConnection(sqlite3.Connection):
    """A connection where asking for WAL fails twice while another process holds a lock."""

    attempts = 0

    def execute(self, sql: str, *args: Any) -> sqlite3.Cursor:
        """Raise on the first two requests for WAL."""
        if sql == "PRAGMA journal_mode=WAL":
            WalBriefLockConnection.attempts += 1
            if WalBriefLockConnection.attempts <= 2:
                msg = "database is locked"
                raise sqlite3.OperationalError(msg)
        return super().execute(sql, *args)


def test_wal_retried_while_locked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A brief lock while switching to WAL is waited out without a warning."""
    connect = sqlite3.connect
    monkeypatch.setattr(
        sqlite3, "connect", lambda *a, **kw: connect(*a, factory=WalBriefLockConnection, **kw)
    )
    monkeypatch.setattr(WalBriefLockConnection, "attempts", 0)

    with caplog.at_level(logging.WARNING), sqlite_cache.SqliteCache(tmp_path / "cache.db") as cache:
        assert cache.journal_mode == "wal"
    assert WalBriefLockConnection.attempts == 3
    assert "Couldn't enable WAL" not in caplog.text


def test_legacy_database_is_reset(tmp_path: Path) -> None:
    """A 4.x database's responses table is dropped and replaced on open."""
    db = tmp_path / "cache.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE responses (key, json, expire)")
    con.execute("INSERT INTO responses VALUES ('key', '{\"id\": 1}', '2999-01-01')")
    con.commit()
    con.close()

    with sqlite_cache.SqliteCache(db) as cache:
        tables = {
            row[0]
            for row in cache.con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert tables == {"cache"}
        assert cache.get("key") is None
        cache.store("key", {"id": 2}, resource="series", kind="detail")
        assert cache.get("key") == {"id": 2}


@pytest.mark.parametrize(
    ("setup", "match"),
    [
        (["CREATE TABLE users (id, name)"], r"table 'users'"),
        (["CREATE TABLE cache (id, payload)"], r"table 'cache'"),
        (
            ["CREATE TABLE responses (key, json, expire)", "CREATE TABLE users (id, name)"],
            r"table 'users'",
        ),
        (
            [
                "CREATE TABLE responses (key, json, expire)",
                "CREATE VIEW names AS SELECT key FROM responses",
            ],
            r"view 'names'",
        ),
    ],
)
# Another application may set user_version too, so even 1 doesn't make a database a cache.
@pytest.mark.parametrize("version", [0, sqlite_cache.SCHEMA_VERSION])
def test_foreign_database_refused(
    tmp_path: Path, setup: list[str], match: str, version: int
) -> None:
    """A database with anything but a Mokkari cache in it is left untouched."""
    db = tmp_path / "app.db"
    con = sqlite3.connect(db)
    for statement in setup:
        con.execute(statement)
    con.execute(f"PRAGMA user_version = {version}")
    con.commit()
    before = con.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()
    con.close()

    with pytest.raises(exceptions.CacheError, match=match):
        sqlite_cache.SqliteCache(db)

    con = sqlite3.connect(db)
    assert (
        con.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall() == before
    )
    assert con.execute("PRAGMA user_version").fetchone()[0] == version
    assert con.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    con.close()


def test_newer_schema_refused(tmp_path: Path) -> None:
    """A cache written by a newer Mokkari is refused rather than rebuilt, so its entries survive."""
    db = tmp_path / "cache.db"
    with sqlite_cache.SqliteCache(db) as cache:
        cache.store("key", {"id": 1}, resource="series", kind="detail")
        cache.con.execute(f"PRAGMA user_version = {sqlite_cache.SCHEMA_VERSION + 1}")

    current = sqlite_cache.SCHEMA_VERSION
    match = rf"newer version of Mokkari \(schema {current + 1}; this version reads {current}\)"
    with pytest.raises(exceptions.CacheError, match=match):
        sqlite_cache.SqliteCache(db)

    con = sqlite3.connect(db)
    assert con.execute("PRAGMA user_version").fetchone()[0] == sqlite_cache.SCHEMA_VERSION + 1
    assert con.execute("SELECT key FROM cache").fetchall() == [("key",)]
    con.close()


def test_older_schema_rebuilt(tmp_path: Path) -> None:
    """A cache written by an older Mokkari 5 is dropped and rebuilt at the current version."""
    db = tmp_path / "cache.db"
    with sqlite_cache.SqliteCache(db) as cache:
        cache.store("key", {"id": 1}, resource="series", kind="detail")
        cache.con.execute("PRAGMA user_version = 0")

    with sqlite_cache.SqliteCache(db) as cache:
        assert cache.get("key") is None
        assert cache.con.execute("PRAGMA user_version").fetchone()[0] == sqlite_cache.SCHEMA_VERSION


def test_current_version_without_table_rebuilt(tmp_path: Path) -> None:
    """An empty database that only has the current user_version gets the cache table."""
    db = tmp_path / "cache.db"
    con = sqlite3.connect(db)
    con.execute(f"PRAGMA user_version = {sqlite_cache.SCHEMA_VERSION}")
    con.close()

    with sqlite_cache.SqliteCache(db) as cache:
        cache.store("key", {"id": 1}, resource="series", kind="detail")
        assert cache.get("key") == {"id": 1}


def test_concurrent_open_creates_schema_once(tmp_path: Path) -> None:
    """Caches opening the same new database at once don't collide creating the table."""
    for i in range(10):
        db = tmp_path / f"cache{i}.db"
        with ThreadPoolExecutor(max_workers=8) as pool:
            caches = list(pool.map(sqlite_cache.SqliteCache, [db] * 8))
        for cache in caches:
            cache.close()


# ============================================================================
# Session integration
# ============================================================================


def test_session_caches_detail(
    dummy_api_token: str, make_cache: Callable[..., sqlite_cache.SqliteCache]
) -> None:
    """A detail response is stored with its resource and kind, and served from the cache."""
    cache = make_cache()
    m = api(dummy_api_token, cache=cache)
    url = "https://metron.cloud/api/universe/1/"
    body = {
        "id": 1,
        "name": "Earth 2",
        "modified": "2024-01-01T12:00:00Z",
        "publisher": {"id": 1, "name": "DC Comics"},
        "designation": "Earth 2",
        "desc": "",
        "resource_url": "https://metron.cloud/universe/earth-2/",
    }

    with requests_mock.Mocker() as r:
        r.get(url, json=body)
        assert m.universe(1).name == "Earth 2"
        assert m.universe(1).name == "Earth 2"
        assert r.call_count == 1

    row = cache.con.execute("SELECT resource, kind FROM cache WHERE key = ?", (url,)).fetchone()
    assert row == ("universe", "detail")


def test_session_caches_paginated_list(
    dummy_api_token: str, make_cache: Callable[..., sqlite_cache.SqliteCache]
) -> None:
    """Every page of a list is stored under the first page's scope, and served from the cache."""
    cache = make_cache()
    m = api(dummy_api_token, cache=cache)
    page1 = "https://metron.cloud/api/role/?name=writer"
    page2 = "https://metron.cloud/api/role/?name=writer&page=2"

    with requests_mock.Mocker() as r:
        # requests_mock tries the most recently registered matcher first.
        r.get(page1, json={"count": 2, "next": page2, "results": [{"id": 1, "name": "Writer"}]})
        r.get(page2, json={"count": 2, "next": None, "results": [{"id": 2, "name": "Co-Writer"}]})

        first = m.role_list({"name": "writer"})
        second = m.role_list({"name": "writer"})
        assert r.call_count == 2

    assert [role.name for role in first] == ["Writer", "Co-Writer"]
    assert second == first
    rows = cache.con.execute("SELECT key, resource, kind FROM cache ORDER BY key").fetchall()
    assert rows == [(page1, "role", "list"), (page2, "role", "list")]


ROLE_PAGE1 = "https://metron.cloud/api/role/?name=writer"
ROLE_PAGE2 = "https://metron.cloud/api/role/?name=writer&page=2"


def role_page(next_page: str | None, *names: str) -> dict[str, Any]:
    """Return a page of a role list response."""
    results = [{"id": i, "name": name} for i, name in enumerate(names, 1)]
    return {"count": len(names), "next": next_page, "results": results}


@pytest.mark.parametrize("missing", [ROLE_PAGE1, ROLE_PAGE2])
def test_session_refetches_whole_paginated_list(
    missing: str, dummy_api_token: str, make_cache: Callable[..., sqlite_cache.SqliteCache]
) -> None:
    """If any page of a list is missing from the cache, every page is fetched again."""
    cache = make_cache()
    m = api(dummy_api_token, cache=cache)

    with requests_mock.Mocker() as r:
        r.get(ROLE_PAGE1, json=role_page(ROLE_PAGE2, "Writer"))
        r.get(ROLE_PAGE2, json=role_page(None, "Co-Writer"))
        m.role_list({"name": "writer"})

        cache.delete(missing)
        r.get(ROLE_PAGE1, json=role_page(ROLE_PAGE2, "Writer (new)"))
        r.get(ROLE_PAGE2, json=role_page(None, "Co-Writer (new)"))
        roles = m.role_list({"name": "writer"})

        assert [role.name for role in roles] == ["Writer (new)", "Co-Writer (new)"]
        assert r.call_count == 4

    assert cache.get(ROLE_PAGE1) == role_page(ROLE_PAGE2, "Writer (new)")
    assert cache.get(ROLE_PAGE2) == role_page(None, "Co-Writer (new)")


def test_session_refetch_ends_at_new_single_page(
    dummy_api_token: str, make_cache: Callable[..., sqlite_cache.SqliteCache]
) -> None:
    """A list refetched because a page was missing may now fit on a single page."""
    cache = make_cache()
    m = api(dummy_api_token, cache=cache)

    with requests_mock.Mocker() as r:
        r.get(ROLE_PAGE1, json=role_page(ROLE_PAGE2, "Writer"))
        r.get(ROLE_PAGE2, json=role_page(None, "Co-Writer"))
        m.role_list({"name": "writer"})

        cache.delete(ROLE_PAGE2)
        r.get(ROLE_PAGE1, json=role_page(None, "Writer"))
        roles = m.role_list({"name": "writer"})

        assert [role.name for role in roles] == ["Writer"]
        assert r.call_count == 3


def test_session_does_not_cache_pull_list(
    dummy_api_token: str, make_cache: Callable[..., sqlite_cache.SqliteCache]
) -> None:
    """The pull list is fetched every time, since user data isn't cached by default."""
    cache = make_cache()
    m = api(dummy_api_token, cache=cache)
    body = {
        "count": 1,
        "next": None,
        "results": [
            {
                "id": 1,
                "series_count": 3,
                "series_url": "https://metron.cloud/api/pull_list/series/",
                "modified": "2024-01-01T12:00:00Z",
            }
        ],
    }

    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/pull_list/", json=body)
        m.pull_list()
        m.pull_list()
        assert r.call_count == 2

    assert count_rows(cache) == 0


def test_session_does_not_modify_cached_pages(dummy_api_token: str) -> None:
    """A cache that stores and returns objects by reference keeps each page as fetched."""

    class DictCache(NoGet):
        def __init__(self) -> None:
            self.data: dict[str, Any] = {}

        def get(self, key: str) -> Any | None:
            return self.data.get(key)

        def store(self, key: str, value: Any, *, resource: str, kind: str) -> None:  # noqa: ARG002
            self.data[key] = value

    cache = DictCache()
    m = api(dummy_api_token, cache=cache)  # type: ignore[arg-type]

    with requests_mock.Mocker() as r:
        r.get(ROLE_PAGE1, json=role_page(ROLE_PAGE2, "Writer"))
        r.get(ROLE_PAGE2, json=role_page(None, "Co-Writer"))
        lists = [m.role_list({"name": "writer"}) for _ in range(3)]
        assert r.call_count == 2

    for roles in lists:
        assert [role.name for role in roles] == ["Writer", "Co-Writer"]
    assert [role["name"] for role in cache.data[ROLE_PAGE1]["results"]] == ["Writer"]


# ============================================================================
# Invalidation after writes
# ============================================================================


class RecordingCache:
    """A cache that records which resources Session invalidates."""

    def __init__(self) -> None:
        """Start with nothing invalidated."""
        self.invalidated: list[str] = []

    def get(self, key: str) -> Any | None:  # noqa: ARG002
        """Retrieve no data."""
        return None

    def store(self, key: str, value: Any, *, resource: str, kind: str) -> None:  # noqa: ARG002
        """Save no data."""
        return

    def invalidate(self, resource: str) -> int:
        """Record the resource."""
        self.invalidated.append(resource)
        return 0


class FailingInvalidateCache(RecordingCache):
    """A cache whose invalidate() fails, e.g. because its database is locked."""

    def invalidate(self, resource: str) -> int:  # noqa: ARG002
        """Fail."""
        msg = "database is locked"
        raise sqlite3.OperationalError(msg)


def test_session_write_invalidates_cache(
    dummy_api_token: str, make_cache: Callable[..., sqlite_cache.SqliteCache]
) -> None:
    """A read after a successful write fetches the new data instead of the cached copy."""
    m = api(dummy_api_token, cache=make_cache())
    url = "https://metron.cloud/api/universe/1/"
    body = {
        "id": 1,
        "name": "Earth 2",
        "modified": "2024-01-01T12:00:00Z",
        "publisher": {"id": 1, "name": "DC Comics"},
        "designation": "Earth 2",
        "desc": "",
        "resource_url": "https://metron.cloud/universe/earth-2/",
    }
    patched = {**body, "name": "Earth Two", "publisher": 1}

    with requests_mock.Mocker() as r:
        r.get(url, json=body)
        assert m.universe(1).name == "Earth 2"
        r.patch(url, json=patched)
        m.universe_patch(1, UniversePost(name="Earth Two"))
        r.get(url, json={**body, "name": "Earth Two"})
        assert m.universe(1).name == "Earth Two"
        assert r.call_count == 3


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        (["series"], ("series",)),
        (["series", 5], ("series",)),
        (["credit"], ("credit", "issue")),
        (["variant"], ("variant", "issue")),
        (["wish_list", "items", 5, "acquire"], ("wish_list", "collection")),
        (["wish_list", "items", 5, "remove"], ("wish_list",)),
    ],
)
def test_written_resources(endpoint: list[str | int], expected: tuple[str, ...]) -> None:
    """A write invalidates its own resource and any others it changes."""
    assert session._written_resources(endpoint) == expected


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        (["series"], "series"),
        (["series", 5], "series"),
        (["series", 5, "issue_list"], "issue"),
        (["character", 5, "issue_list"], "issue"),
        (["reading_list", 5, "items"], "reading_list"),
    ],
)
def test_cached_resource(endpoint: list[str | int], expected: str) -> None:
    """A resource's issue list is cached as issues, everything else as its own resource."""
    assert session._cached_resource(endpoint) == expected


def test_issue_write_invalidates_issue_lists(
    dummy_api_token: str, make_cache: Callable[..., sqlite_cache.SqliteCache]
) -> None:
    """Invalidating issues drops a series' cached issue list."""
    cache = make_cache(empty_list_ttl=timedelta(hours=1))
    m = api(dummy_api_token, cache=cache)
    url = "https://metron.cloud/api/series/5/issue_list/"
    body = {"count": 0, "next": None, "previous": None, "results": []}

    with requests_mock.Mocker() as r:
        r.get(url, json=body)
        m.series_issues_list(5)
        m.series_issues_list(5)
        assert r.call_count == 1
        cache.invalidate("issue")
        m.series_issues_list(5)
        assert r.call_count == 2


def test_void_write_invalidates_cache(dummy_api_token: str) -> None:
    """A write with no response body invalidates the cache too."""
    cache = RecordingCache()
    m = api(dummy_api_token, cache=cache)  # type: ignore[arg-type]

    with requests_mock.Mocker() as r:
        r.post("https://metron.cloud/api/wish_list/items/5/acquire/", status_code=204)
        m.wish_list_acquire_item(5, AcquireWishListItem())

    assert cache.invalidated == ["wish_list", "collection"]


def test_failed_write_does_not_invalidate(dummy_api_token: str) -> None:
    """Nothing is invalidated when the write fails."""
    cache = RecordingCache()
    m = api(dummy_api_token, cache=cache)  # type: ignore[arg-type]

    with requests_mock.Mocker() as r:
        r.delete("https://metron.cloud/api/collection/5/", status_code=404)
        with pytest.raises(exceptions.ApiError):
            m.collection_delete(5)

    assert cache.invalidated == []


def test_failing_invalidate_is_logged(
    dummy_api_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A cache that fails to invalidate doesn't turn a successful write into an error."""
    m = api(dummy_api_token, cache=FailingInvalidateCache())  # type: ignore[arg-type]

    with requests_mock.Mocker() as r:
        r.delete("https://metron.cloud/api/collection/5/", status_code=204)
        m.collection_delete(5)

    assert "Cache invalidate('collection') failed" in caplog.text


# ============================================================================
# Cache failures
# ============================================================================


class LockedCache(RecordingCache):
    """A cache whose database stays locked, failing every get() and store()."""

    def get(self, key: str) -> Any | None:  # noqa: ARG002
        """Fail."""
        msg = "database is locked"
        raise sqlite3.OperationalError(msg)

    def store(self, key: str, value: Any, *, resource: str, kind: str) -> None:  # noqa: ARG002
        """Fail."""
        msg = "database is locked"
        raise sqlite3.OperationalError(msg)


def test_failing_cache_get_fetches_from_metron(
    dummy_api_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A cache that can't be read is treated as a miss rather than failing the request."""
    m = api(dummy_api_token, cache=LockedCache())  # type: ignore[arg-type]

    with requests_mock.Mocker() as r:
        r.get(ROLE_PAGE1, json=role_page(None, "Writer"))
        roles = m.role_list({"name": "writer"})

    assert [role.name for role in roles] == ["Writer"]
    assert "Cache get() failed" in caplog.text


def test_failing_cache_store_keeps_fetched_pages(
    dummy_api_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A cache that can't be written doesn't throw away the pages already fetched."""
    m = api(dummy_api_token, cache=LockedCache())  # type: ignore[arg-type]

    with requests_mock.Mocker() as r:
        r.get(ROLE_PAGE1, json=role_page(ROLE_PAGE2, "Writer"))
        r.get(ROLE_PAGE2, json=role_page(None, "Co-Writer"))
        roles = m.role_list({"name": "writer"})

    assert [role.name for role in roles] == ["Writer", "Co-Writer"]
    assert f"Cache store() failed; not caching {ROLE_PAGE2}" in caplog.text


# ============================================================================
# Per-user data
# ============================================================================

READING_LIST_URL = "https://metron.cloud/api/reading_list/3/"
READING_LIST_BODY = {
    "id": 3,
    "name": "Private List",
    "slug": "private-list",
    "user": {"id": 1, "username": "alice"},
    "desc": "",
    "list_type": "Custom",
    "is_private": True,
    "attribution_source": "",
    "attribution_url": "",
    "average_rating": None,
    "rating_count": 0,
    "items_url": "https://metron.cloud/api/reading_list/3/items/",
    "resource_url": "https://metron.cloud/reading-lists/private-list/",
    "modified": "2024-01-01T12:00:00Z",
}


def test_per_user_data_not_shared_between_tokens(
    make_cache: Callable[..., sqlite_cache.SqliteCache],
) -> None:
    """A reading list cached for one token isn't served to another token sharing the cache."""
    cache = make_cache()
    alice = api("alice-token", cache=cache)
    bob = api("bob-token", cache=cache)

    with requests_mock.Mocker() as r:
        r.get(READING_LIST_URL, json=READING_LIST_BODY)
        alice.reading_list(3)
        alice.reading_list(3)
        assert r.call_count == 1
        r.get(READING_LIST_URL, status_code=404, json={"detail": "Not found."})
        with pytest.raises(exceptions.ApiError):
            bob.reading_list(3)
        assert r.call_count == 2

    keys = [row[0] for row in cache.con.execute("SELECT key FROM cache")]
    assert len(keys) == 1
    assert keys[0].startswith(f"{READING_LIST_URL}#user=")
    assert "alice-token" not in keys[0]


def test_shared_data_shared_between_tokens(
    make_cache: Callable[..., sqlite_cache.SqliteCache],
) -> None:
    """Reference data isn't per-user, so one token's cached copy is served to another."""
    cache = make_cache()
    alice = api("alice-token", cache=cache)
    bob = api("bob-token", cache=cache)

    with requests_mock.Mocker() as r:
        r.get(ROLE_PAGE1, json=role_page(None, "Writer"))
        alice.role_list({"name": "writer"})
        bob.role_list({"name": "writer"})
        assert r.call_count == 1


def test_per_user_pages_scoped(make_cache: Callable[..., sqlite_cache.SqliteCache]) -> None:
    """Every page of a per-user list is scoped to the token, not only the first."""
    cache = make_cache(ttl={"collection": timedelta(minutes=10)}, empty_list_ttl=None)
    m = api("alice-token", cache=cache)
    page1 = "https://metron.cloud/api/collection/"
    page2 = "https://metron.cloud/api/collection/?page=2"

    with requests_mock.Mocker() as r:
        r.get(page1, json={"count": 0, "next": page2, "results": []})
        r.get(page2, json={"count": 0, "next": None, "results": []})
        m.collections_list()
        m.collections_list()
        assert r.call_count == 2

    keys = sorted(row[0] for row in cache.con.execute("SELECT key FROM cache"))
    assert [key.partition("#user=")[:2] for key in keys] == [(page1, "#user="), (page2, "#user=")]

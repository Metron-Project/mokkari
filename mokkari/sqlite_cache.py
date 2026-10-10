"""SQLite Cache module.

This module provides the following classes:

- Cache: Protocol for a response cache passed to ``Session``
- SqliteCache
"""

from __future__ import annotations

__all__ = [
    "DEFAULT_TTLS",
    "NO_CACHE",
    "RESOURCES",
    "Cache",
    "CacheKind",
    "NoCache",
    "SqliteCache",
    "Ttl",
]

import json
import logging
import sqlite3
import threading
import time
from datetime import timedelta
from enum import Enum
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    Literal,
    Protocol,
    Self,
    get_args,
    runtime_checkable,
)

from mokkari import exceptions

if TYPE_CHECKING:
    import os
    from collections.abc import Mapping

LOGGER = logging.getLogger(__name__)

CacheKind = Literal["detail", "list"]
_KINDS: Final[frozenset[str]] = frozenset(get_args(CacheKind))

RESOURCES: Final[frozenset[str]] = frozenset(
    {
        "arc",
        "character",
        "collection",
        "creator",
        "imprint",
        "issue",
        "publisher",
        "pull_list",
        "reading_list",
        "role",
        "series",
        "series_type",
        "team",
        "universe",
        "wish_list",
    }
)
"""The resources ``Session`` caches responses under, for use in ``SqliteCache``'s ``ttl``."""

# How long, in seconds, to wait for another connection (possibly in another process) to
# release its lock before giving up with "database is locked".
_BUSY_TIMEOUT: Final[float] = 5.0


class NoCache(Enum):
    """Type of ``NO_CACHE``, the TTL that keeps a resource out of the cache."""

    NO_CACHE = "NO_CACHE"

    def __repr__(self) -> str:
        """Return ``"NO_CACHE"``."""
        return "NO_CACHE"


NO_CACHE: Final = NoCache.NO_CACHE
"""TTL for a resource that isn't cached at all.

A distinct sentinel rather than ``timedelta(0)``: in Mokkari 4.x ``expire=0`` meant
"never expire", so a falsy value meaning "don't cache" would silently disable caching
for anyone porting that setting. A zero ``timedelta`` is rejected instead.
"""

Ttl = timedelta | NoCache | None
"""A lifetime, ``None`` to never expire, or ``NO_CACHE`` to not cache at all."""

# Per-user data changes whenever the user edits it on Metron, and serving a stale copy is more
# surprising than for shared reference data, so it isn't cached unless the caller opts back in.
DEFAULT_TTLS: Final[Mapping[str, Ttl]] = MappingProxyType(
    {
        "collection": NO_CACHE,
        "pull_list": NO_CACHE,
        "wish_list": NO_CACHE,
    }
)

# Bumped whenever the table layout changes. An older database is dropped and recreated rather
# than migrated, since everything in it can be fetched again; a newer one is refused.
SCHEMA_VERSION: Final[int] = 1

_SCHEMA: Final[str] = """
CREATE TABLE cache (
    key TEXT PRIMARY KEY,
    resource TEXT NOT NULL,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL
);
CREATE INDEX idx_cache_resource ON cache(resource, kind);
CREATE INDEX idx_cache_expires ON cache(expires_at);
"""

# The tables a Mokkari cache may hold, and columns they're recognised by. ``responses`` is the
# table Mokkari 4.x used; ``cache`` keeps these columns across schema versions.
_OWN_TABLES: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "responses": frozenset({"key", "json", "expire"}),
        "cache": frozenset({"key", "resource", "kind", "value"}),
    }
)

_PURGE_EXPIRED: Final[str] = "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at <= ?"


@runtime_checkable
class Cache(Protocol):
    """Protocol for a response cache passed to ``Session``.

    Pass an object implementing this protocol as ``Session(cache=...)`` (or
    ``api(..., cache=...)``). ``SqliteCache`` is the bundled implementation.
    Implementations must be safe to call concurrently from multiple threads
    sharing one ``Session``.

    A cache may also have an ``invalidate(resource)`` method. If it does, ``Session``
    calls it after each successful write, with the resource written to and any others
    the write may have changed, so later reads don't return the pre-write copy.
    """

    def get(self, key: str) -> Any | None:
        """Return the unexpired value stored under ``key``, or ``None`` if there isn't one."""
        ...

    def store(self, key: str, value: Any, *, resource: str, kind: CacheKind) -> None:
        """Store ``value`` under ``key``, replacing any existing entry.

        ``resource`` is the first segment of the endpoint (e.g. ``"series"``), and
        ``kind`` is ``"detail"`` for a single object or ``"list"`` for a list
        endpoint, including every page of a paginated one. An implementation may
        use them to decide how long to keep the entry, or whether to keep it at all.
        """
        ...


def _check_ttl_key(name: str) -> None:
    """Raise ``ValueError`` unless ``name`` is a ``ttl`` key that ``ttl_for`` can match."""
    resource, sep, kind = name.partition(":")
    if sep and kind not in _KINDS:
        msg = f"TTL key {name!r} has an unknown kind {kind!r}: use one of {sorted(_KINDS)}"
        raise ValueError(msg)
    if resource == "*":
        if not sep:
            msg = "TTL key '*' needs a kind, e.g. '*:list'. Use default_ttl for everything else."
            raise ValueError(msg)
        return
    if resource not in RESOURCES:
        msg = (
            f"TTL key {name!r} has an unknown resource {resource!r}: use one of {sorted(RESOURCES)}"
        )
        raise ValueError(msg)


def _shorter(a: Ttl, b: Ttl) -> Ttl:
    """Return whichever of two TTLs keeps an entry for less time."""
    if a is NO_CACHE or b is NO_CACHE:
        return NO_CACHE
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


class SqliteCache:
    """A response cache backed by SQLite, with a configurable lifetime per resource.

    How long an entry lives is looked up by ``"{resource}:{kind}"``, then by
    ``"{resource}"``, then by ``"*:{kind}"`` (e.g. ``"*:list"`` for every list
    endpoint), then falls back to ``default_ttl``. A TTL is a positive
    ``timedelta``, ``None`` (or ``SqliteCache.NEVER``) for an entry that never
    expires, or ``NO_CACHE`` (or ``SqliteCache.NO_CACHE``) for one that isn't
    cached at all. ``collection``, ``pull_list`` and ``wish_list`` default to
    ``NO_CACHE`` (see ``DEFAULT_TTLS``); add them to ``ttl`` to cache them anyway.

    A list response with no results is kept for at most ``empty_list_ttl``, so a
    search that found nothing doesn't outlive the data arriving on Metron. By
    default empty lists aren't cached at all.

    Safe to share across threads: all database access goes through a single
    connection guarded by an internal lock, since sqlite3 connections aren't
    safe for concurrent use from multiple threads on their own.

    Uses SQLite's WAL journal mode where it can, so readers in other processes
    aren't blocked while one writes. Where WAL isn't available, such as on some
    network filesystems, the cache logs a warning and carries on in SQLite's
    default journal mode; ``journal_mode`` says which one is in use.

    ``close()`` releases the connection, but the cache stays usable: the next
    call reopens it, so a long-lived cache can be closed between runs like a
    ``requests.Session``. A closed ``":memory:"`` cache reopens empty.

    Opening a database written by an older version of Mokkari discards its contents.
    One written by a newer version, or holding anything else, is refused with ``CacheError``
    rather than replaced.

    Examples:
        >>> from datetime import timedelta
        >>> cache = SqliteCache(
        ...     "mokkari_cache.db",
        ...     default_ttl=timedelta(days=7),
        ...     ttl={
        ...         "issue:list": timedelta(hours=6),
        ...         "issue": timedelta(days=2),
        ...         "role": SqliteCache.NEVER,
        ...         "collection": timedelta(minutes=10),
        ...         "series:list": SqliteCache.NO_CACHE,
        ...         "*:list": timedelta(days=1),
        ...     },
        ...     empty_list_ttl=timedelta(minutes=30),
        ... )
    """

    NEVER: Final = None
    NO_CACHE: Final = NO_CACHE

    def __init__(
        self,
        db_name: str | os.PathLike[str] = "mokkari_cache.db",
        *,
        default_ttl: Ttl = timedelta(days=7),
        ttl: Mapping[str, Ttl] | None = None,
        empty_list_ttl: Ttl = NO_CACHE,
    ) -> None:
        """Open (or create) the cache database and purge any expired entries.

        Args:
            db_name: Path to the SQLite database, or ``":memory:"``.
            default_ttl: Lifetime for resources without an entry in ``ttl``.
                ``None`` never expires them, and ``NO_CACHE`` caches nothing by default.
            ttl: Lifetimes keyed by ``"{resource}:{kind}"``, ``"{resource}"`` or
                ``"*:{kind}"``, merged over ``DEFAULT_TTLS``. ``resource`` is one of
                ``RESOURCES`` and ``kind`` is ``"detail"`` or ``"list"``.
            empty_list_ttl: The longest a list response with no results is kept.
                It only ever shortens the usual TTL: ``NO_CACHE`` doesn't cache
                empty lists, and ``None`` gives them the usual TTL.

        Raises:
            TypeError: If any TTL isn't a ``timedelta``, ``None`` or ``NO_CACHE``.
            ValueError: If any TTL is zero or negative, or a ``ttl`` key names an unknown
                resource or kind.
            CacheError: If ``db_name`` is a database with tables other than a Mokkari cache's,
                or a cache written by a newer version of Mokkari.
        """
        for name in ttl or {}:
            _check_ttl_key(name)
        self._ttl = {**DEFAULT_TTLS, **(ttl or {})}
        self.default_ttl = default_ttl
        self.empty_list_ttl = empty_list_ttl
        for name, value in [
            ("default_ttl", default_ttl),
            ("empty_list_ttl", empty_list_ttl),
            *self._ttl.items(),
        ]:
            if value is None or value is NO_CACHE:
                continue
            if not isinstance(value, timedelta):
                msg = f"TTL for {name!r} must be a timedelta, None or NO_CACHE, not {value!r}"
                raise TypeError(msg)
            if value <= timedelta(0):
                msg = (
                    f"TTL for {name!r} must be positive: {value}. "
                    "Use NO_CACHE to keep it out of the cache, or None to never expire it."
                )
                raise ValueError(msg)

        self._db_name = db_name
        self._lock = threading.Lock()
        self._con: sqlite3.Connection | None = None
        self.journal_mode = ""
        # Open now rather than on first use, so a bad path fails here.
        with self._lock:
            self._connection()

    @property
    def con(self) -> sqlite3.Connection:
        """The database connection, reopened if the cache was closed.

        Not guarded by the cache's lock, so don't use it while other threads use the cache.
        """
        with self._lock:
            return self._connection()

    def _connection(self) -> sqlite3.Connection:
        """Return the connection, opening it first if needed. The caller must hold the lock.

        Opening checks and creates or resets the table, sets the journal mode, and purges expired
        entries.
        """
        if self._con is not None:
            return self._con
        con = sqlite3.connect(self._db_name, timeout=_BUSY_TIMEOUT, check_same_thread=False)
        try:
            # The schema is checked first, so a file that isn't a cache is left untouched.
            self._init_schema(con)
            self.journal_mode = self._enable_wal(con)
            with con:
                con.execute(_PURGE_EXPIRED, (time.time(),))
        except BaseException:
            con.close()
            raise
        self._con = con
        return con

    @staticmethod
    def _enable_wal(con: sqlite3.Connection) -> str:
        """Switch to WAL if possible and return the journal mode now in use.

        It's a cache, so falling back to another mode is better than refusing to open.
        """
        # Switching needs an exclusive lock, and SQLite reports "locked" at once rather than
        # waiting out the busy timeout, so retry while another process opens the same file.
        deadline = time.monotonic() + _BUSY_TIMEOUT
        while True:
            try:
                (mode,) = con.execute("PRAGMA journal_mode=WAL").fetchone()
                break
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and time.monotonic() < deadline:
                    time.sleep(0.01)
                    continue
                (mode,) = con.execute("PRAGMA journal_mode").fetchone()
                LOGGER.warning("Couldn't enable WAL for the cache, using %r mode: %s", mode, e)
                return mode
        # An in-memory database ignores the request and stays in "memory" mode.
        if mode not in ("wal", "memory"):
            LOGGER.warning("Couldn't enable WAL for the cache, using %r mode", mode)
        return mode

    @staticmethod
    def _init_schema(con: sqlite3.Connection) -> None:
        """Create the table, discarding any older layout and refusing a newer one."""
        (version,) = con.execute("PRAGMA user_version").fetchone()
        if version == SCHEMA_VERSION:
            return
        with con:
            # sqlite3 doesn't open a transaction for DDL, so take the write lock explicitly
            # and check again, in case another process rebuilt the schema first.
            con.execute("BEGIN IMMEDIATE")
            (version,) = con.execute("PRAGMA user_version").fetchone()
            if version == SCHEMA_VERSION:
                return
            # Rebuilding a newer layout would wipe the cache of the newer Mokkari sharing this
            # file, which would then wipe ours, on every open.
            if version > SCHEMA_VERSION:
                msg = (
                    f"The cache database was written by a newer version of Mokkari (schema "
                    f"{version}; this version reads {SCHEMA_VERSION}). Upgrade Mokkari, or give "
                    "this cache a file of its own."
                )
                raise exceptions.CacheError(msg)
            if foreign := SqliteCache._foreign_objects(con):
                msg = (
                    f"Not a Mokkari cache database, refusing to replace it: it has {foreign}. "
                    "Give SqliteCache a file of its own."
                )
                raise exceptions.CacheError(msg)
            con.execute("DROP TABLE IF EXISTS responses")
            con.execute("DROP TABLE IF EXISTS cache")
            for statement in _SCHEMA.split(";"):
                if statement.strip():
                    con.execute(statement)
            con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @staticmethod
    def _foreign_objects(con: sqlite3.Connection) -> list[str]:
        """Return the tables, views and triggers in the database that a Mokkari cache didn't make."""
        foreign = []
        for kind, name in con.execute(
            "SELECT type, name FROM sqlite_master "
            "WHERE type IN ('table', 'view', 'trigger') AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\'"
        ):
            columns = _OWN_TABLES.get(name) if kind == "table" else None
            if columns is not None:
                found = {row[1] for row in con.execute(f"PRAGMA table_info({name})")}
                if columns <= found:
                    continue
            foreign.append(f"{kind} {name!r}")
        return foreign

    def ttl_for(self, resource: str, kind: CacheKind) -> Ttl:
        """Return how long an entry for ``resource`` and ``kind`` is kept.

        Returns:
            The lifetime, ``None`` if it never expires, or ``NO_CACHE`` if it isn't cached.
        """
        for name in (f"{resource}:{kind}", resource, f"*:{kind}"):
            if name in self._ttl:
                return self._ttl[name]
        return self.default_ttl

    def get(self, key: str) -> Any | None:
        """Retrieve unexpired data from the cache database.

        Args:
            key: The cache key, normally the request URL.

        Returns:
            The stored data, or ``None`` if it's missing or expired.
        """
        with self._lock:
            con = self._connection()
            row = con.execute(
                "SELECT value FROM cache WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)",
                (key, time.time()),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def store(self, key: str, value: Any, *, resource: str, kind: CacheKind) -> None:
        """Save data to the cache database, replacing any existing entry for ``key``.

        Nothing is stored when the TTL for ``resource`` and ``kind`` is ``NO_CACHE``.
        A list response with no results is kept for no longer than ``empty_list_ttl``.

        Args:
            key: The cache key, normally the request URL.
            value: JSON-serializable data to store.
            resource: The first segment of the endpoint, e.g. ``"series"``.
            kind: ``"detail"`` or ``"list"``.
        """
        ttl = self.ttl_for(resource, kind)
        if kind == "list" and isinstance(value, dict) and value.get("count") == 0:
            ttl = _shorter(ttl, self.empty_list_ttl)
        if ttl is NO_CACHE:
            return
        now = time.time()
        expires_at = None if ttl is None else now + ttl.total_seconds()
        with self._lock, self._connection() as con:
            con.execute(
                "INSERT INTO cache(key, resource, kind, value, created_at, expires_at) "
                "VALUES(?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET resource = excluded.resource, "
                "kind = excluded.kind, value = excluded.value, "
                "created_at = excluded.created_at, expires_at = excluded.expires_at",
                (key, resource, kind, json.dumps(value), now, expires_at),
            )

    def delete(self, key: str) -> bool:
        """Remove the entry for ``key``.

        Returns:
            ``True`` if an entry was removed.
        """
        return self._delete("DELETE FROM cache WHERE key = ?", (key,)) > 0

    def invalidate(self, resource: str, kind: CacheKind | None = None) -> int:
        """Remove every entry for ``resource``, or only those of ``kind`` if given.

        ``Session`` calls this after each of its own writes. Call it yourself after
        changing data on Metron some other way, such as through the website.

        Returns:
            The number of entries removed.
        """
        if kind is None:
            return self._delete("DELETE FROM cache WHERE resource = ?", (resource,))
        return self._delete("DELETE FROM cache WHERE resource = ? AND kind = ?", (resource, kind))

    def clear(self) -> int:
        """Remove every entry.

        Returns:
            The number of entries removed.
        """
        return self._delete("DELETE FROM cache", ())

    def cleanup(self) -> int:
        """Remove expired entries. Expired entries are never returned, so this only reclaims space.

        Returns:
            The number of entries removed.
        """
        return self._delete(_PURGE_EXPIRED, (time.time(),))

    def _delete(self, sql: str, params: tuple[Any, ...]) -> int:
        with self._lock, self._connection() as con:
            return con.execute(sql, params).rowcount

    def close(self) -> None:
        """Close the database connection. Safe to call more than once.

        The cache can still be used afterwards; the next call reopens the connection.
        """
        with self._lock:
            if self._con is not None:
                self._con.close()
                self._con = None

    def __enter__(self) -> Self:
        """Enter the context manager, returning this cache."""
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Exit the context manager, closing the database connection."""
        self.close()

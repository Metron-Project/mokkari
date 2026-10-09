"""SQLite Cache module.

This module provides the following classes:

- Cache: Protocol for a response cache passed to ``Session``
- SqliteCache
"""

from __future__ import annotations

__all__ = ["DEFAULT_TTLS", "Cache", "CacheKind", "SqliteCache"]

import json
import sqlite3
import threading
import time
from datetime import timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol, Self

if TYPE_CHECKING:
    import os
    from collections.abc import Mapping

CacheKind = Literal["detail", "list"]

# Per-user data changes whenever the user edits it on Metron, and serving a stale copy is more
# surprising than for shared reference data, so it isn't cached unless the caller opts back in.
DEFAULT_TTLS: Final[Mapping[str, timedelta | None]] = MappingProxyType(
    {
        "collection": timedelta(0),
        "pull_list": timedelta(0),
        "wish_list": timedelta(0),
    }
)

# Bumped whenever the table layout changes. An older database is dropped and recreated rather
# than migrated, since everything in it can be fetched again.
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


class Cache(Protocol):
    """Protocol for a response cache passed to ``Session``.

    Pass an object implementing this protocol as ``Session(cache=...)`` (or
    ``api(..., cache=...)``). ``SqliteCache`` is the bundled implementation.
    Implementations must be safe to call concurrently from multiple threads
    sharing one ``Session``.
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


class SqliteCache:
    """A response cache backed by SQLite, with a configurable lifetime per resource.

    How long an entry lives is looked up by ``"{resource}:{kind}"``, then by
    ``"{resource}"``, then falls back to ``default_ttl``. A TTL of ``None`` means
    the entry never expires, and ``timedelta(0)`` means it isn't cached at all.
    ``collection``, ``pull_list`` and ``wish_list`` default to ``timedelta(0)``
    (see ``DEFAULT_TTLS``); add them to ``ttl`` to cache them anyway.

    Safe to share across threads: all database access goes through a single
    connection guarded by an internal lock, since sqlite3 connections aren't
    safe for concurrent use from multiple threads on their own.

    Opening a database written by an older version of Mokkari discards its contents.

    Examples:
        >>> from datetime import timedelta
        >>> cache = SqliteCache(
        ...     "mokkari_cache.db",
        ...     default_ttl=timedelta(days=7),
        ...     ttl={
        ...         "issue:list": timedelta(hours=6),
        ...         "issue": timedelta(days=2),
        ...         "role": None,
        ...         "collection": timedelta(minutes=10),
        ...     },
        ... )
    """

    def __init__(
        self,
        db_name: str | os.PathLike[str] = "mokkari_cache.db",
        *,
        default_ttl: timedelta | None = timedelta(days=7),
        ttl: Mapping[str, timedelta | None] | None = None,
    ) -> None:
        """Open (or create) the cache database and purge any expired entries.

        Args:
            db_name: Path to the SQLite database, or ``":memory:"``.
            default_ttl: Lifetime for resources without an entry in ``ttl``.
                ``None`` never expires them.
            ttl: Lifetimes keyed by ``"{resource}:{kind}"`` or ``"{resource}"``,
                merged over ``DEFAULT_TTLS``.

        Raises:
            ValueError: If any TTL is negative.
        """
        self._ttl = {**DEFAULT_TTLS, **(ttl or {})}
        self.default_ttl = default_ttl
        for name, value in [("default_ttl", default_ttl), *self._ttl.items()]:
            if value is not None and value < timedelta(0):
                msg = f"TTL for {name!r} must not be negative: {value}"
                raise ValueError(msg)

        self._lock = threading.Lock()
        self.con = sqlite3.connect(db_name, check_same_thread=False)
        with self._lock:
            self._init_schema()
        self.cleanup()

    def _init_schema(self) -> None:
        """Create the table, discarding any older layout. The caller must hold the lock."""
        # WAL lets readers in other processes keep going while one writes. An in-memory
        # database ignores it and stays in "memory" mode.
        self.con.execute("PRAGMA journal_mode=WAL")
        (version,) = self.con.execute("PRAGMA user_version").fetchone()
        if version == SCHEMA_VERSION:
            return
        with self.con:
            # ``responses`` is the table Mokkari 4.x used.
            self.con.execute("DROP TABLE IF EXISTS responses")
            self.con.execute("DROP TABLE IF EXISTS cache")
            for statement in _SCHEMA.split(";"):
                if statement.strip():
                    self.con.execute(statement)
            self.con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def ttl_for(self, resource: str, kind: CacheKind) -> timedelta | None:
        """Return how long an entry for ``resource`` and ``kind`` is kept.

        Returns:
            The lifetime, ``None`` if it never expires, or ``timedelta(0)`` if it isn't cached.
        """
        for name in (f"{resource}:{kind}", resource):
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
            row = self.con.execute(
                "SELECT value FROM cache WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)",
                (key, time.time()),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def store(self, key: str, value: Any, *, resource: str, kind: CacheKind) -> None:
        """Save data to the cache database, replacing any existing entry for ``key``.

        Nothing is stored when the TTL for ``resource`` and ``kind`` is ``timedelta(0)``.

        Args:
            key: The cache key, normally the request URL.
            value: JSON-serializable data to store.
            resource: The first segment of the endpoint, e.g. ``"series"``.
            kind: ``"detail"`` or ``"list"``.
        """
        ttl = self.ttl_for(resource, kind)
        if ttl is not None and not ttl:
            return
        now = time.time()
        expires_at = None if ttl is None else now + ttl.total_seconds()
        with self._lock, self.con:
            self.con.execute(
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

        Useful after changing data on Metron, e.g. ``invalidate("series")`` after
        ``series_patch()``.

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
        return self._delete(
            "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at <= ?", (time.time(),)
        )

    def _delete(self, sql: str, params: tuple[Any, ...]) -> int:
        with self._lock, self.con:
            return self.con.execute(sql, params).rowcount

    def close(self) -> None:
        """Close the database connection. Safe to call more than once."""
        with self._lock:
            self.con.close()

    def __enter__(self) -> Self:
        """Enter the context manager, returning this cache."""
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Exit the context manager, closing the database connection."""
        self.close()

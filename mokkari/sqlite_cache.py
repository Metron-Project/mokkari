"""SQLite Cache module.

This module provides the following classes:

- SqliteCache
"""

from __future__ import annotations

__all__ = ["SqliteCache"]

import json
import logging
import sqlite3
import threading
import time
from datetime import timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, Self

from mokkari import exceptions
from mokkari.cache import NO_CACHE, TtlPolicy

if TYPE_CHECKING:
    import os
    from collections.abc import Mapping

    from mokkari.cache import CacheKind, Ttl

LOGGER = logging.getLogger(__name__)

# How long, in seconds, to wait for another connection (possibly in another process) to
# release its lock before giving up with "database is locked".
_BUSY_TIMEOUT: Final[float] = 5.0


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


class SqliteCache:
    """A response cache backed by SQLite, with a configurable lifetime per resource.

    How long each entry is kept follows ``TtlPolicy``: ``ttl`` sets a lifetime per
    resource and kind, ``default_ttl`` covers the rest, and empty lists are kept
    for at most ``empty_list_ttl``. ``SqliteCache.NEVER`` and ``SqliteCache.NO_CACHE``
    are the same as ``None`` and ``NO_CACHE``.

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
        self.ttl_policy = TtlPolicy(default_ttl=default_ttl, ttl=ttl, empty_list_ttl=empty_list_ttl)

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
        if SqliteCache._is_current(con):
            return
        with con:
            # sqlite3 doesn't open a transaction for DDL, so take the write lock explicitly
            # and check again, in case another process rebuilt the schema first.
            con.execute("BEGIN IMMEDIATE")
            if SqliteCache._is_current(con):
                return
            (version,) = con.execute("PRAGMA user_version").fetchone()
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
    def _is_current(con: sqlite3.Connection) -> bool:
        """Return whether the database is a Mokkari cache at the current schema version.

        ``user_version`` alone isn't enough, since other applications set it too.
        """
        (version,) = con.execute("PRAGMA user_version").fetchone()
        if version != SCHEMA_VERSION:
            return False
        has_cache = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'cache'"
        ).fetchone()
        return has_cache is not None and not SqliteCache._foreign_objects(con)

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
        return self.ttl_policy.ttl_for(resource, kind)

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
        ttl = self.ttl_policy.ttl_for_value(value, resource=resource, kind=kind)
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

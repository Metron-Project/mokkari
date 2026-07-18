"""SQLite Cache module.

This module provides the following classes:

- SqliteCache
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any


class SqliteCache:
    """A class for caching data using SQLite.

    Safe to share across threads: all database access goes through a single
    connection guarded by an internal lock, since sqlite3 connections aren't
    safe for concurrent use from multiple threads on their own.

    Methods:
        - __init__: Initializes a new SqliteCache.
        - get: Retrieve data from the cache database.
        - store: Save data to the cache database.
        - cleanup: Remove any expired data from the cache database.
        - _determine_expire_str: Determine the expiration date string for cache data.
    """

    def __init__(
        self: SqliteCache,
        db_name: str = "mokkari_cache.db",
        expire: int | None = None,
    ) -> None:
        """Initialize a new SqliteCache."""
        self.expire = expire
        self._lock = threading.Lock()
        self.con = sqlite3.connect(db_name, check_same_thread=False)
        with self._lock:
            self.con.execute("CREATE TABLE IF NOT EXISTS responses (key, json, expire)")
        self.cleanup()

    def get(self: SqliteCache, key: str) -> Any | None:
        """Retrieve data from the cache database.

        Args:
            key: A string representing the value to search for.

        Returns:
            The retrieved data if found, or None if not found.
        """
        with self._lock:
            result = self.con.execute("SELECT json FROM responses WHERE key = ?", (key,)).fetchone()
        return json.loads(result[0]) if result else None

    def store(self: SqliteCache, key: str, value: str) -> None:
        """Save data to the cache database.

        Args:
            key: A string representing the item id.
            value: The data to be saved.

        Returns:
            None
        """
        with self._lock:
            self.con.execute(
                "INSERT INTO responses(key, json, expire) VALUES(?, ?, ?)",
                (key, json.dumps(value), self._determine_expire_str()),
            )
            self.con.commit()

    def cleanup(self: SqliteCache) -> None:
        """Remove any expired data from the cache database."""
        if not self.expire:
            return
        with self._lock:
            self.con.execute(
                "DELETE FROM responses WHERE expire < ?;",
                (datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),),
            )
            self.con.commit()

    def _determine_expire_str(self: SqliteCache) -> str:
        """Determine the expiration date string for cache data."""
        dt = (
            datetime.now(tz=timezone.utc) + timedelta(days=self.expire)
            if self.expire
            else datetime.now(tz=timezone.utc)
        )
        return dt.strftime("%Y-%m-%d")

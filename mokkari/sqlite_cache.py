"""SQLite Cache module.

This module provides the following classes:

- SqliteCache
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any


class SqliteCache:
    """A class for caching data using SQLite.

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
        self.con = sqlite3.connect(db_name)
        self.cur = self.con.cursor()
        self.cur.execute("CREATE TABLE IF NOT EXISTS responses (key, json, expire)")
        self.cleanup()

    def get(self: SqliteCache, key: str) -> Any | None:
        """Retrieve data from the cache database.

        Args:
            key: A string representing the value to search for.

        Returns:
            The retrieved data if found, or None if not found.
        """
        self.cur.execute("SELECT json FROM responses WHERE key = ?", (key,))
        return json.loads(result[0]) if (result := self.cur.fetchone()) else None

    def store(self: SqliteCache, key: str, value: str) -> None:
        """Save data to the cache database.

        Args:
            key: A string representing the item id.
            value: The data to be saved.

        Returns:
            None
        """
        self.cur.execute(
            "INSERT INTO responses(key, json, expire) VALUES(?, ?, ?)",
            (key, json.dumps(value), self._determine_expire_str()),
        )
        self.con.commit()

    def cleanup(self: SqliteCache) -> None:
        """Remove any expired data from the cache database."""
        if not self.expire:
            return
        self.cur.execute(
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

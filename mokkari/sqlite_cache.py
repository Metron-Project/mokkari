"""SQLite Cache module.

This module provides the following classes:

- SqliteCache
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any


class SqliteCache:
    """The SqliteCache object to cache search results from Metron.

    Args:
    ----
        db_name (str): Path and database name to use.
        expire (int, optional): The number of days to keep the cache results
        before they expire.

    """

    def __init__(
        self: "SqliteCache",
        db_name: str = "mokkari_cache.db",
        expire: int | None = None,
    ) -> None:
        """Initialize a new SqliteCache."""
        self.expire = expire
        self.con = sqlite3.connect(db_name)
        self.cur = self.con.cursor()
        self.cur.execute("CREATE TABLE IF NOT EXISTS responses (key, json, expire)")
        self.cleanup()

    def get(self: "SqliteCache", key: str) -> Any | None:
        """Retrieve data from the cache database.

        Args:
        ----
            key (str): value to search for.

        """
        self.cur.execute("SELECT json FROM responses WHERE key = ?", (key,))
        return json.loads(result[0]) if (result := self.cur.fetchone()) else None

    def store(self: "SqliteCache", key: str, value: str) -> None:
        """Save data to the cache database.

        Args:
        ----
            key (str): Item id.
            value (str): data to save.

        """
        self.cur.execute(
            "INSERT INTO responses(key, json, expire) VALUES(?, ?, ?)",
            (key, json.dumps(value), self._determine_expire_str()),
        )
        self.con.commit()

    def cleanup(self: "SqliteCache") -> None:
        """Remove any expired data from the cache database."""
        if not self.expire:
            return
        self.cur.execute(
            "DELETE FROM responses WHERE expire < ?;",
            (datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),),
        )
        self.con.commit()

    def _determine_expire_str(self: "SqliteCache") -> str:
        dt = (
            datetime.now(tz=timezone.utc) + timedelta(days=self.expire)
            if self.expire
            else datetime.now(tz=timezone.utc)
        )
        return dt.strftime("%Y-%m-%d")

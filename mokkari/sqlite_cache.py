"""
SQLite Cache module.

This module provides the following classes:

- SqliteCache
"""
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional


class SqliteCache:
    """
    The SqliteCache object to cache search results from Metron.

    :param str db_name: Path and database name to use.
    :param expire: The number of days to keep the cache results before they expire.
    :type expire: int, optional
    """

    def __init__(
        self, db_name: str = "mokkari_cache.db", expire: Optional[int] = None
    ) -> None:
        """Intialize a new SqliteCache."""
        self.expire = expire
        self.con = sqlite3.connect(db_name)
        self.cur = self.con.cursor()
        self.cur.execute("CREATE TABLE IF NOT EXISTS responses (key, json, expire)")
        self.cleanup()

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve data from the cache database.

        :param str key: value to search for.
        """
        self.cur.execute("SELECT json FROM responses WHERE key = ?", (key,))
        if result := self.cur.fetchone():
            return json.loads(result[0])

        return None

    def store(self, key: str, value: str) -> None:
        """
        Save data to the cache database.

        :param str key: Item id.
        :param str value: data to save.
        """
        self.cur.execute(
            "INSERT INTO responses(key, json, expire) VALUES(?, ?, ?)",
            (key, json.dumps(value), self._determine_expire_str()),
        )
        self.con.commit()

    def cleanup(self) -> None:
        """Remove any expired data from the cache database."""
        if not self.expire:
            return
        self.cur.execute(
            "DELETE FROM responses WHERE expire < ?;",
            (datetime.now().strftime("%Y-%m-%d"),),
        )
        self.con.commit()

    def _determine_expire_str(self) -> str:
        if self.expire:
            dt = datetime.now() + timedelta(days=self.expire)
        else:
            dt = datetime.now()
        return dt.strftime("%Y-%m-%d")

"""
SQLite Cache module.

This module provides the following classes:

- SqliteCache
"""
import json
import sqlite3


class SqliteCache:
    """
    The SqliteCache object to cache search results from Metron.

    :param str db_name: Path and database name to use.
    """

    def __init__(self, db_name: str = "mokkari_cache.db"):
        """Intialize a new SqliteCache."""
        self.con = sqlite3.connect(db_name)
        self.cur = self.con.cursor()
        self.cur.execute("CREATE TABLE IF NOT EXISTS responses (key, json)")

    def get(self, key: str):
        """
        Retrieve data from the cache database.

        :param str key: value to search for.
        """
        self.cur.execute("SELECT json FROM responses WHERE key = ?", (key,))
        result = self.cur.fetchone()

        if result:
            return json.loads(result[0])

        return None

    def store(self, key: str, value: str):
        """
        Save data to the cache database.

        :param str key: Item id.
        :param str value: data to save.
        """
        self.cur.execute(
            "INSERT INTO responses(key, json) VALUES(?, ?)", (key, json.dumps(value))
        )
        self.con.commit()

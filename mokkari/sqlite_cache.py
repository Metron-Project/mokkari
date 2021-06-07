import json
import sqlite3


class SqliteCache:
    def __init__(self, db_name: str = "mokkari_cache.db"):
        self.con = sqlite3.connect(db_name)
        self.cur = self.con.cursor()
        self.cur.execute("CREATE TABLE IF NOT EXISTS responses (key, json)")

    def get(self, key: str):
        self.cur.execute("SELECT json FROM responses WHERE key = ?", (key,))
        result = self.cur.fetchone()

        if result:
            return json.loads(result[0])

        return None

    def store(self, key: str, value: str):
        self.cur.execute(
            "INSERT INTO responses(key, json) VALUES(?, ?)", (key, json.dumps(value))
        )
        self.con.commit()

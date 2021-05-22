import json
import os
import unittest

import requests_mock
from mokkari import api, exceptions, sqlite_cache


class NoGet:
    def store(self, key, value):
        # This method should store key value pair
        return


class NoStore:
    def get(self, key):
        return None


class TestCache(unittest.TestCase):
    def setUp(self):
        self.username = os.getenv("METRON_USERNAME", "username")
        self.passwd = os.getenv("METRON_PASSWD", "passwd")

    def test_no_get(self):
        m = api(username=self.username, passwd=self.passwd, cache=NoGet())

        with self.assertRaises(exceptions.CacheError):
            m.series(5)

    def test_no_store(self):
        m = api(username=self.username, passwd=self.passwd, cache=NoStore())

        with requests_mock.Mocker() as r:
            r.get(
                "https://metron.cloud/api/series/5/",
                text='{"response_code": 200}',
            )

            with self.assertRaises(exceptions.CacheError):
                m.series(5)

    def test_sql_store(self):
        fresh_cache = sqlite_cache.SqliteCache(":memory:")
        test_cache = sqlite_cache.SqliteCache("tests/testing_mock.sqlite")

        m = api(username=self.username, passwd=self.passwd, cache=fresh_cache)
        url = "https://metron.cloud/api/series/1/"

        self.assertTrue(fresh_cache.get(url) is None)

        try:
            with requests_mock.Mocker() as r:
                r.get(url, text=json.dumps(test_cache.get(url)))
                m.series(1)

            self.assertTrue(fresh_cache.get(url) is not None)
        except TypeError:
            print(
                "This test will fail after cache db deleted.\n"
                "It should pass if you now re-run the test suite without deleting the database."
            )
            assert False


if __name__ == "__main__":
    unittest.main()

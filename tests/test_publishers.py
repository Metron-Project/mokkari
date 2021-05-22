import os
import unittest

from mokkari import api, exceptions, sqlite_cache
from mokkari.publishers_list import PublishersList


class TestPublishers(unittest.TestCase):
    def setUp(self):
        username = os.getenv("METRON_USERNAME", "username")
        passwd = os.getenv("METRON_PASSWD", "passwd")
        self.c = api(
            username=username,
            passwd=passwd,
            cache=sqlite_cache.SqliteCache("tests/testing_mock.sqlite"),
        )

    def test_known_publishers(self):
        marvel = self.c.publisher(1)
        self.assertTrue(marvel.name == "Marvel")
        self.assertTrue(
            marvel.image
            == "https://static.metron.cloud/media/publisher/2018/11/11/marvel.jpg"
        )
        self.assertTrue(marvel.wikipedia == "Marvel_Comics")
        self.assertTrue(marvel.founded == 1939)

    def test_publisherlist(self):
        publishers = self.c.publishers_list()
        self.assertGreater(len(publishers.publishers), 0)

    def test_bad_publisher(self):
        with self.assertRaises(exceptions.ApiError):
            self.c.publisher(-1)

    def test_bad_response_data(self):
        with self.assertRaises(exceptions.ApiError):
            PublishersList({"results": {"name": 1}})


if __name__ == "__main__":
    unittest.main()

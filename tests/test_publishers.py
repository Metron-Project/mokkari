import os
import unittest

import mokkari

# TODO: Should mock the responses but for now let's use live data


class TestPublishers(unittest.TestCase):
    def setUp(self):
        username = os.getenv("METRON_USERNAME", "username")
        passwd = os.getenv("METRON_PASSWD", "passwd")
        self.c = mokkari.api(username=username, passwd=passwd)

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


if __name__ == "__main__":
    unittest.main()

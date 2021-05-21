import os
import unittest

from mokkari import api, exceptions
from mokkari.arcs_list import ArcsList

# TODO: Should mock the responses but for now let's use live data


class TestArcs(unittest.TestCase):
    def setUp(self):
        username = os.getenv("METRON_USERNAME", "username")
        passwd = os.getenv("METRON_PASSWD", "passwd")
        self.c = api(username=username, passwd=passwd)

    def test_known_arc(self):
        heroes = self.c.arc(1)
        self.assertTrue(heroes.name == "Heroes In Crisis")
        self.assertTrue(
            heroes.image
            == "https://static.metron.cloud/media/arc/2018/11/12/heroes-in-crisis.jpeg"
        )

    def test_arcslist(self):
        arcs = self.c.arcs_list()
        self.assertGreater(len(arcs.arcs), 0)

    def test_bad_arc(self):
        with self.assertRaises(exceptions.ApiError):
            self.c.arc(-1)

    def test_bad_response_data(self):
        with self.assertRaises(exceptions.ApiError):
            ArcsList({"results": {"name": 1}})


if __name__ == "__main__":
    unittest.main()

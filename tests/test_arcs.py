import os
import unittest

import mokkari

# TODO: Should mock the responses but for now let's use live data


class TestArcs(unittest.TestCase):
    def setUp(self):
        username = os.getenv("METRON_USERNAME", "username")
        passwd = os.getenv("METRON_PASSWD", "passwd")
        self.c = mokkari.api(username=username, passwd=passwd)

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


if __name__ == "__main__":
    unittest.main()

import datetime
from mokkari.creators_list import CreatorsList
import os
import unittest

from requests import models

import mokkari

# TODO: Should mock the responses but for now let's use live data


class TestCreator(unittest.TestCase):
    def setUp(self):
        username = os.getenv("METRON_USERNAME", "username")
        passwd = os.getenv("METRON_PASSWD", "passwd")
        self.c = mokkari.api(username=username, passwd=passwd)

    def test_known_creator(self):
        jack = self.c.creator(3)
        self.assertTrue(jack.name == "Jack Kirby")
        self.assertTrue(jack.birth == datetime.date(1917, 8, 28))
        self.assertTrue(jack.death == datetime.date(1994, 2, 6))
        self.assertTrue(
            jack.image
            == "https://static.metron.cloud/media/creator/2018/11/11/432124-Jack_Kirby01.jpg"
        )
        self.assertTrue(jack.wikipedia == "Jack_Kirby")

    def test_comiclist(self):
        creators = self.c.creators_list()
        self.assertGreater(len(creators.creators), 0)


if __name__ == "__main__":
    unittest.main()
import os
import unittest

import mokkari

# TODO: Should mock the responses but for now let's use live data


class TestCreator(unittest.TestCase):
    def setUp(self):
        username = os.getenv("METRON_USERNAME", "username")
        passwd = os.getenv("METRON_PASSWD", "passwd")
        self.c = mokkari.api(username=username, passwd=passwd)

    def test_known_character(self):
        black_bolt = self.c.character(1)
        self.assertTrue(black_bolt.name == "Black Bolt")
        self.assertTrue(
            black_bolt.image
            == "https://static.metron.cloud/media/character/2018/11/11/black-bolt.jpg"
        )
        self.assertTrue(black_bolt.wikipedia == "Black_Bolt")

    def test_characterlist(self):
        character = self.c.characters_list()
        self.assertGreater(len(character.characters), 0)


if __name__ == "__main__":
    unittest.main()
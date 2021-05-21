import os
import unittest

from mokkari import api, exceptions
from mokkari.characters_list import CharactersList

# TODO: Should mock the responses but for now let's use live data


class TestCharacters(unittest.TestCase):
    def setUp(self):
        username = os.getenv("METRON_USERNAME", "username")
        passwd = os.getenv("METRON_PASSWD", "passwd")
        self.c = api(username=username, passwd=passwd)

    def test_known_character(self):
        black_bolt = self.c.character(1)
        self.assertTrue(black_bolt.name == "Black Bolt")
        self.assertTrue(
            black_bolt.image
            == "https://static.metron.cloud/media/character/2018/11/11/black-bolt.jpg"
        )
        self.assertTrue(black_bolt.wikipedia == "Black_Bolt")
        self.assertTrue(len(black_bolt.creators) == 2)
        self.assertTrue(len(black_bolt.teams) == 2)

    def test_characterlist(self):
        character = self.c.characters_list()
        self.assertGreater(len(character.characters), 0)

    def test_bad_issue(self):
        with self.assertRaises(exceptions.ApiError):
            self.c.issue(-1)

    def test_bad_response_data(self):
        with self.assertRaises(exceptions.ApiError):
            CharactersList({"results": {"name": 1}})


if __name__ == "__main__":
    unittest.main()

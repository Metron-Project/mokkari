import os
import unittest

import mokkari

# TODO: Should mock the responses but for now let's use live data


class TestTeams(unittest.TestCase):
    def setUp(self):
        username = os.getenv("METRON_USERNAME", "username")
        passwd = os.getenv("METRON_PASSWD", "passwd")
        self.c = mokkari.api(username=username, passwd=passwd)

    def test_known_team(self):
        inhumans = self.c.team(1)
        self.assertTrue(inhumans.name == "Inhumans")
        self.assertTrue(
            inhumans.image
            == "https://static.metron.cloud/media/team/2018/11/11/Inhumans.jpg"
        )
        self.assertTrue(inhumans.wikipedia == "Inhumans")
        self.assertTrue(len(inhumans.creators) == 2)

    def test_teamlist(self):
        teams = self.c.teams_list()
        self.assertGreater(len(teams.teams), 0)


if __name__ == "__main__":
    unittest.main()

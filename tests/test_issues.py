import os
import unittest
import datetime

import mokkari

# TODO: Should mock the responses but for now let's use live data


class TestIssues(unittest.TestCase):
    def setUp(self):
        username = os.getenv("METRON_USERNAME", "username")
        passwd = os.getenv("METRON_PASSWD", "passwd")
        self.c = mokkari.api(username=username, passwd=passwd)

    def test_known_issue(self):
        death = self.c.issue(1)
        self.assertTrue(death.publisher.name == "Marvel")
        self.assertTrue(death.series.name == "Death of the Inhumans")
        self.assertTrue(death.volume == 1)
        self.assertTrue(death.name[0] == "Chapter One: Vox")
        self.assertTrue(death.cover_date == datetime.date(2018, 9, 1))
        self.assertTrue(death.store_date == datetime.date(2018, 7, 4))
        self.assertTrue(
            death.image
            == "https://static.metron.cloud/media/issue/2018/11/11/6497376-01.jpg"
        )
        self.assertGreater(len(death.characters), 0)
        self.assertGreater(len(death.teams), 0)
        self.assertGreater(len(death.credits), 0)

    def test_issueslist(self):
        issues = self.c.issues_list()
        self.assertGreater(len(issues.issues), 0)


if __name__ == "__main__":
    unittest.main()

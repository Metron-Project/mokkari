import datetime
import os
import unittest

from mokkari import api, exceptions, sqlite_cache
from mokkari.issues_list import IssuesList


class TestIssues(unittest.TestCase):
    def setUp(self):
        username = os.getenv("METRON_USERNAME", "username")
        passwd = os.getenv("METRON_PASSWD", "passwd")
        self.c = api(
            username=username,
            passwd=passwd,
            cache=sqlite_cache.SqliteCache("tests/testing_mock.sqlite"),
        )

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

    def test_bad_issue(self):
        with self.assertRaises(exceptions.ApiError):
            self.c.issue(-1)

    def test_bad_response_data(self):
        with self.assertRaises(exceptions.ApiError):
            IssuesList({"results": {"volume": "1"}})


if __name__ == "__main__":
    unittest.main()

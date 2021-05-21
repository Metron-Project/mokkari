import os
import unittest

from mokkari import api, exceptions
from mokkari.series_list import SeriesList

# TODO: Should mock the responses but for now let's use live data


class TestSeries(unittest.TestCase):
    def setUp(self):
        username = os.getenv("METRON_USERNAME", "username")
        passwd = os.getenv("METRON_PASSWD", "passwd")
        self.c = api(username=username, passwd=passwd)

    def test_known_series(self):
        death = self.c.series(1)
        self.assertTrue(death.name == "Death of the Inhumans")
        self.assertTrue(death.sort_name == "Death of the Inhumans")
        self.assertTrue(death.volume == 1)
        self.assertTrue(death.year_began == 2018)
        self.assertTrue(death.year_end == 2018)
        self.assertTrue(death.issue_count == 5)
        self.assertTrue(
            death.image
            == "https://static.metron.cloud/media/issue/2018/11/11/6497376-01.jpg"
        )

    def test_serieslist(self):
        series = self.c.series_list()
        self.assertGreater(len(series.series), 0)

    def test_bad_series(self):
        with self.assertRaises(exceptions.ApiError):
            self.c.series(-1)

    def test_bad_response_data(self):
        with self.assertRaises(exceptions.ApiError):
            SeriesList({"results": {"name": 1}})


if __name__ == "__main__":
    unittest.main()

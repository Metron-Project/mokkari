from mokkari import series
import os
import unittest

import mokkari

# TODO: Should mock the responses but for now let's use live data


class TestSeries(unittest.TestCase):
    def setUp(self):
        username = os.getenv("METRON_USERNAME", "username")
        passwd = os.getenv("METRON_PASSWD", "passwd")
        self.c = mokkari.api(username=username, passwd=passwd)

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


if __name__ == "__main__":
    unittest.main()

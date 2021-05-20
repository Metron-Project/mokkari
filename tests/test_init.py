import unittest

import mokkari
from mokkari.exceptions import AuthenticationError


class TestInit(unittest.TestCase):
    def setUp(self):
        pass

    def test_api(self):
        with self.assertRaises(AuthenticationError):
            mokkari.api()

        with self.assertRaises(AuthenticationError):
            mokkari.api(passwd="Something")

        with self.assertRaises(AuthenticationError):
            mokkari.api(username="Something")

        m = None
        try:
            m = mokkari.api(username="Something", passwd="Else")
        except Exception as exc:
            self.fail("mokkari.api() raised {} unexpectedly!".format(exc))

        self.assertEquals(m.__class__.__name__, mokkari.sesssion.Session.__name__)


if __name__ == "__main__":
    unittest.main()

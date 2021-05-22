import unittest

from mokkari import api, exceptions, sesssion


class TestInit(unittest.TestCase):
    def setUp(self):
        pass

    def test_api(self):
        with self.assertRaises(exceptions.AuthenticationError):
            api()

        with self.assertRaises(exceptions.AuthenticationError):
            api(passwd="Something")

        with self.assertRaises(exceptions.AuthenticationError):
            api(username="Something")

        m = None
        try:
            m = api(username="Something", passwd="Else")
        except Exception as exc:
            self.fail("mokkari.api() raised {} unexpectedly!".format(exc))

        self.assertEqual(m.__class__.__name__, sesssion.Session.__name__)


if __name__ == "__main__":
    unittest.main()

import pytest

from mokkari import api, exceptions, session


def test_api():
    with pytest.raises(exceptions.AuthenticationError):
        api()

    with pytest.raises(exceptions.AuthenticationError):
        api(passwd="Something")

    with pytest.raises(exceptions.AuthenticationError):
        api(username="Something")

    m = None
    try:
        m = api(username="Something", passwd="Else")
    except Exception as exc:
        print("mokkari.api() raised {} unexpectedly!".format(exc))

    assert m.__class__.__name__ == session.Session.__name__

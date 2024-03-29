# ruff: noqa: S106
"""Test Init module.

This module contains tests for project init.
"""

import pytest

from mokkari import api, exceptions, session


def test_api() -> None:
    """Test for api()."""
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
        print(f"mokkari.api() raised {exc} unexpectedly!")

    assert m.__class__.__name__ == session.Session.__name__

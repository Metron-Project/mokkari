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
    except Exception as exc:  # noqa: BLE001
        print(f"mokkari.api() raised {exc} unexpectedly!")

    assert m.__class__.__name__ == session.Session.__name__

    m = None
    try:
        m = api(api_token="Something")
    except Exception as exc:  # noqa: BLE001
        print(f"mokkari.api() raised {exc} unexpectedly!")

    assert m.__class__.__name__ == session.Session.__name__


def test_api_forwards_rate_limiter() -> None:
    """api() forwards a rate_limiter object through to the Session it constructs."""
    sentinel = object()

    m = api(username="Something", passwd="Else", rate_limiter=sentinel)

    assert m.rate_limiter is sentinel

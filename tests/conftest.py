"""Conftest module.

This module contains pytest fixtures.
"""

import json
import os
from collections.abc import Callable
from typing import Any

import pytest
import requests

from mokkari import api
from mokkari.session import Session

MakeResponse = Callable[..., requests.Response]


@pytest.fixture
def make_response() -> MakeResponse:
    """Return a factory for real ``requests.Response`` objects.

    For tests that replace the HTTP session's ``request`` rather than mock a URL. A real
    response behaves like Metron's, e.g. ``raise_for_status()`` raises for a 4xx or 5xx.
    """

    def make(
        status_code: int = 200,
        *,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        response = requests.Response()
        response.status_code = status_code
        response.headers.update(headers or {})
        response._content = b"" if json_body is None else json.dumps(json_body).encode()
        return response

    return make


@pytest.fixture(scope="session")
def dummy_api_token() -> str:
    """API token fixture."""
    return os.getenv("METRON_API_TOKEN", "token")


@pytest.fixture(scope="session")
def talker(dummy_api_token: str) -> Session:
    """Mokkari api fixture."""
    return api(dummy_api_token)

"""Conftest module.

This module contains pytest fixtures.
"""

import os

import pytest

from mokkari import api
from mokkari.session import Session


@pytest.fixture(scope="session")
def dummy_api_token() -> str:
    """API token fixture."""
    return os.getenv("METRON_API_TOKEN", "token")


@pytest.fixture(scope="session")
def talker(dummy_api_token: str) -> Session:
    """Mokkari api fixture."""
    return api(api_token=dummy_api_token)

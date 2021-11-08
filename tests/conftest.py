"""
Conftest module.

This module contains pytest fixtures.
"""

from pathlib import Path

import pytest

from mokkari import api


@pytest.fixture(scope="session")
def talker():
    """Mokkari api fixture."""
    return api(username="dummy_username", passwd="dummy_password")


@pytest.fixture(scope="session")
def arc_resp():
    """Single arc fixture."""
    return (Path(__file__).parent / "data/arc.json").read_text()


@pytest.fixture(scope="session")
def arc_list_resp():
    """Arc list fixture."""
    return (Path(__file__).parent / "data/arc_list.json").read_text()


@pytest.fixture(scope="session")
def character_resp():
    """Character fixture."""
    return (Path(__file__).parent / "data/character.json").read_text()


@pytest.fixture(scope="session")
def character_list_resp():
    """Character list fixture."""
    return (Path(__file__).parent / "data/character_list.json").read_text()

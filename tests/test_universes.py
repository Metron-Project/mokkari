"""Test Universes module.

This module contains tests for Universe objects.
"""

import json

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.schemas.universe import Universe
from mokkari.session import Session


def test_known_universe(talker: Session) -> None:
    """Test for a known universe object."""
    dceased = talker.universe(83)
    assert isinstance(dceased, Universe)
    assert dceased.name == "DCeased"
    assert dceased.designation == "Earth 55"
    assert dceased.publisher.name == "DC Comics"
    assert dceased.publisher.id == 2
    assert dceased.resource_url.__str__() == "https://metron.cloud/universe/dceased/"


def test_universe_list(talker: Session) -> None:
    """Test the Universe list."""
    universes = talker.universes_list()
    universes_iter = iter(universes)
    assert next(universes_iter).name == "2099 AD - Marvel Knights"
    assert next(universes_iter).name == "ABC"
    assert next(universes_iter).name == "AP Superverse"
    assert universes[2].name == "AP Superverse"


def test_bad_universe(talker: Session) -> None:
    """Test for a non-existent team."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/universe/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.universe(-1)


def test_bad_universe_validate(talker: Session) -> None:
    """Test data with invalid data."""
    # Change the 'name' field to an int, when it should be a string.
    data = {
        "id": 150,
        "publisher": 1,
        "name": 50,
        "desc": "Foo Bat",
        "image": "https://static.metron.cloud/media/team/2019/06/20/aquamarines.jpg",
        "modified": "2019-06-23T15:13:23.927059-04:00",
    }

    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/universe/150/",
            text=json.dumps(data),
        )

        with pytest.raises(exceptions.ApiError):
            talker.universe(150)

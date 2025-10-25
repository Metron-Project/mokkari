"""Test Imprints module.

This module contains tests for Imprint objects.
"""

import json

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.session import Session


def test_known_imprints(talker: Session) -> None:
    """Test for a known publisher."""
    vertigo = talker.imprint(1)
    assert vertigo.name == "Vertigo Comics"
    assert (
        vertigo.image.__str__()
        == "https://static.metron.cloud/media/imprint/2024/08/12/vertigo.jpg"
    )
    assert vertigo.founded == 1993
    assert vertigo.publisher.name == "DC Comics"
    assert vertigo.resource_url.__str__() == "https://metron.cloud/imprint/vertigo-comics/"


def test_imprint_list(talker: Session) -> None:
    """Test the ImprintList."""
    imprints = talker.imprints_list()
    imprints_iter = iter(imprints)
    assert next(imprints_iter).name == "Abrams Fanfare"
    assert next(imprints_iter).name == "Action Lab Danger Zone"
    assert next(imprints_iter).name == "Adventure Comics"
    assert len(imprints) == 44
    assert imprints[2].name == "Adventure Comics"


def test_bad_imprint(talker: Session) -> None:
    """Test for a non-existent imprint."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/imprint/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.imprint(-1)


def test_bad_imprint_validate(talker: Session) -> None:
    """Test data with invalid data."""
    # Change the 'name' field to an int, when it should be a string.
    data = {
        "id": 15,
        "name": 150,
        "founded": 1993,
        "desc": "Foo Bar",
        "image": "https://static.metron.cloud/media/imprint/2018/12/02/bongo.png",
        "modified": "2019-06-23T15:13:23.581612-04:00",
    }

    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/imprint/15/",
            text=json.dumps(data),
        )

        with pytest.raises(exceptions.ApiError):
            talker.imprint(15)

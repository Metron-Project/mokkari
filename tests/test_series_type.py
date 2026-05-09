"""Test Series Type.

This module contains tests for SeriesType objects.
"""

import json

import requests_mock

from mokkari.session import Session


def test_series_type_list(talker: Session) -> None:
    """Test the SeriesTypeList."""
    data = {
        "count": 4,
        "next": None,
        "previous": None,
        "results": [
            {"id": 1, "name": "Annual", "modified": "2019-06-23T15:13:19.432378-04:00"},
            {"id": 2, "name": "Digital Chapter", "modified": "2019-06-23T15:13:19.432378-04:00"},
            {"id": 3, "name": "Graphic Novel", "modified": "2019-06-23T15:13:19.432378-04:00"},
            {"id": 4, "name": "Hardcover", "modified": "2019-06-23T15:13:19.432378-04:00"},
        ],
    }
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/series_type/", text=json.dumps(data))
        series_types = talker.series_type_list()
    st_iter = iter(series_types)
    assert next(st_iter).name == "Annual"
    assert next(st_iter).name == "Digital Chapter"
    assert series_types[3].name == "Hardcover"
    assert len(series_types) == 4

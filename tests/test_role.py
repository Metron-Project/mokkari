"""Test Role api.

This module contains tests for Role objects.
"""

import json

import requests_mock

from mokkari.session import Session


def test_role_list(talker: Session) -> None:
    """Test the RoleList."""
    data = {
        "count": 4,
        "next": None,
        "previous": None,
        "results": [
            {"id": 1, "name": "Editor", "modified": "2019-06-23T15:13:19.432378-04:00"},
            {
                "id": 2,
                "name": "Consulting Editor",
                "modified": "2019-06-23T15:13:19.432378-04:00",
            },
            {
                "id": 3,
                "name": "Assistant Editor",
                "modified": "2019-06-23T15:13:19.432378-04:00",
            },
            {"id": 4, "name": "Writer", "modified": "2019-06-23T15:13:19.432378-04:00"},
        ],
    }
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/role/", text=json.dumps(data))
        roles = talker.role_list({"name": "editor"})
    role_iter = iter(roles)
    assert next(role_iter).name == "Editor"
    assert next(role_iter).name == "Consulting Editor"
    assert next(role_iter).name == "Assistant Editor"
    assert len(roles) == 4
    assert roles[1].name == "Consulting Editor"

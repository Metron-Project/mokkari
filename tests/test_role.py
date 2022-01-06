"""
Test Role api.

This module contains tests for Role objects.
"""
import pytest

from mokkari import exceptions, issue


def test_role_list(talker):
    """Test the RoleList."""
    roles = talker.role_list({"name": "editor"})
    role_iter = iter(roles)
    assert next(role_iter).name == "Editor"
    assert next(role_iter).name == "Consulting Editor"
    assert next(role_iter).name == "Assistant Editor"
    assert len(roles) == 10
    assert roles[1].name == "Consulting Editor"


def test_bad_response_data(talker):
    """Test for a bad role response."""
    with pytest.raises(exceptions.ApiError):
        issue.RoleList({"results": {"name": 1}})

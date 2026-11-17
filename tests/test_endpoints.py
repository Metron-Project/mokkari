"""Test the endpoint methods against real Metron-shaped responses.

Each case sends one request through a mocked Metron and validates the response with the
real schema, for endpoints the per-resource test modules don't cover.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import requests_mock

from mokkari import api
from mokkari.schemas.arc import ArcPost
from mokkari.schemas.collection import ScrobbleRequest
from mokkari.schemas.issue import IssuePost
from mokkari.schemas.publisher import PublisherPost
from mokkari.schemas.team import TeamPost
from mokkari.schemas.universe import UniversePost
from mokkari.schemas.wish_list import WishListAddItem

if TYPE_CHECKING:
    from collections.abc import Callable

    from mokkari.session import Session

BASE_URL = "https://metron.cloud/api/"
MODIFIED = "2024-01-01T12:00:00Z"
SERIES = {"id": 1, "name": "Batman", "volume": 1, "year_began": 1940}
ISSUE = {
    "id": 1,
    "series": SERIES,
    "number": "1",
    "cover_date": "2024-01-01",
    "modified": MODIFIED,
}


def page(*results: dict[str, Any]) -> dict[str, Any]:
    """Return a single-page list response holding ``results``."""
    return {"next": None, "previous": None, "results": list(results)}


ARC = {
    "id": 1,
    "name": "Final Crisis",
    "desc": "",
    "resource_url": "https://metron.cloud/arc/final-crisis/",
    "modified": MODIFIED,
}
PUBLISHER = {
    "id": 1,
    "name": "DC Comics",
    "country": "US",
    "desc": "",
    "resource_url": "https://metron.cloud/publisher/dc-comics/",
    "modified": MODIFIED,
}
NAMED = {"id": 1, "name": "Justice League", "modified": MODIFIED}
PULL_LIST_SERIES = {
    "id": 5,
    "series": {**SERIES, "series": "Batman", "modified": MODIFIED},
    "added_on": MODIFIED,
}

# Each case: (call, HTTP method, path under /api/, response body, expected attributes).
# The expected attributes are read from the first item when the call returns a list.
CASES: dict[str, tuple[Callable[[Session], Any], str, str, Any, dict[str, Any]]] = {
    "arc_post": (
        lambda s: s.arc_post(ArcPost(name="Final Crisis")),
        "POST",
        "arc",
        ARC,
        {"name": "Final Crisis"},
    ),
    "arc_patch": (lambda s: s.arc_patch(1, ArcPost(desc="")), "PATCH", "arc/1", ARC, {"id": 1}),
    "publisher_post": (
        lambda s: s.publisher_post(PublisherPost(name="DC Comics")),
        "POST",
        "publisher",
        PUBLISHER,
        {"name": "DC Comics"},
    ),
    "publisher_patch": (
        lambda s: s.publisher_patch(1, PublisherPost(desc="")),
        "PATCH",
        "publisher/1",
        PUBLISHER,
        {"id": 1},
    ),
    "team_post": (
        lambda s: s.team_post(TeamPost(name="Justice League")),
        "POST",
        "team",
        NAMED,
        {"name": "Justice League"},
    ),
    "team_patch": (
        lambda s: s.team_patch(1, TeamPost(desc="")),
        "PATCH",
        "team/1",
        NAMED,
        {"id": 1},
    ),
    "universe_post": (
        lambda s: s.universe_post(UniversePost(name="Earth 2")),
        "POST",
        "universe",
        {**NAMED, "name": "Earth 2"},
        {"name": "Earth 2"},
    ),
    "issue_post": (
        lambda s: s.issue_post(IssuePost(series=1, number="1")),
        "POST",
        "issue",
        {"id": 7, "resource_url": "https://metron.cloud/issue/batman-1940-1/"},
        {"id": 7},
    ),
    "collection": (
        lambda s: s.collection(1),
        "GET",
        "collection/1",
        {
            "id": 1,
            "user": {"id": 1, "username": "testuser"},
            "issue": ISSUE,
            "quantity": 1,
            "book_format": "PRINT",
            "grading_company": "",
            "is_read": True,
            "resource_url": "https://metron.cloud/collection/1/",
            "created_on": MODIFIED,
            "modified": MODIFIED,
        },
        {"book_format": "PRINT", "is_read": True},
    ),
    "collection_missing_issues": (
        lambda s: s.collection_missing_issues(1),
        "GET",
        "collection/missing_issues/1",
        page({"id": 2, "series": SERIES, "number": "2", "cover_date": "2024-02-01"}),
        {"number": "2"},
    ),
    "collection_missing_series": (
        lambda s: s.collection_missing_series(),
        "GET",
        "collection/missing_series",
        page(
            {
                "id": 1,
                "name": "Batman",
                "sort_name": "Batman",
                "year_began": 1940,
                "publisher": {"id": 1, "name": "DC Comics"},
                "series_type": {"id": 1, "name": "Ongoing Series"},
                "total_issues": 713,
                "owned_issues": 500,
                "missing_count": 213,
                "completion_percentage": 70.12,
            }
        ),
        {"name": "Batman", "missing_count": 213},
    ),
    "collection_stats": (
        lambda s: s.collection_stats(),
        "GET",
        "collection/stats",
        {
            "total_items": 200,
            "total_quantity": 250,
            "total_value": "5000.00",
            "read_count": 150,
            "unread_count": 50,
            "by_format": [{"book_format": "PRINT", "count": 180}],
        },
        {"total_items": 200, "unread_count": 50},
    ),
    "collection_scrobble": (
        lambda s: s.collection_scrobble(ScrobbleRequest(issue_id=1, rating=5)),
        "POST",
        "collection/scrobble",
        {
            "id": 100,
            "issue": ISSUE,
            "is_read": True,
            "date_read": MODIFIED,
            "rating": 5,
            "created": True,
            "modified": MODIFIED,
        },
        {"rating": 5, "created": True},
    ),
    "reading_lists_list": (
        lambda s: s.reading_lists_list(),
        "GET",
        "reading_list",
        page(
            {
                "id": 1,
                "name": "My Reading List",
                "slug": "my-reading-list",
                "user": {"id": 1, "username": "testuser"},
                "is_private": False,
                "list_type": "EVENT",
                "attribution_source": "CBRO",
                "average_rating": 4.5,
                "rating_count": 10,
                "modified": MODIFIED,
            }
        ),
        {"name": "My Reading List"},
    ),
    "reading_list_items": (
        lambda s: s.reading_list_items(1),
        "GET",
        "reading_list/1/items",
        page({"id": 1, "issue": ISSUE, "order": 1, "issue_type": "Core"}),
        {"order": 1},
    ),
    "wish_list_items": (
        lambda s: s.wish_list_items(),
        "GET",
        "wish_list/items",
        page({"id": 10, "issue": ISSUE, "status": "Wanted", "priority": 3, "modified": MODIFIED}),
        {"id": 10, "priority": 3},
    ),
    "wish_list_add_item": (
        lambda s: s.wish_list_add_item(WishListAddItem(issue_id=1, priority=2)),
        "POST",
        "wish_list/items/add",
        {
            "id": 10,
            "issue": ISSUE,
            "status": "Wanted",
            "priority": 2,
            "notes": "High priority",
            "added_on": MODIFIED,
            "modified": MODIFIED,
        },
        {"notes": "High priority"},
    ),
    "pull_list_issues": (
        lambda s: s.pull_list_issues({"store_date_after": "2024-01-01"}),
        "GET",
        "pull_list/issues",
        page({**ISSUE, "issue": "Batman #1"}),
        {"number": "1"},
    ),
    "pull_list_series": (
        lambda s: s.pull_list_series(),
        "GET",
        "pull_list/series",
        page(PULL_LIST_SERIES),
        {"id": 5},
    ),
    "pull_list_add_series": (
        lambda s: s.pull_list_add_series(1),
        "POST",
        "pull_list/series/add",
        PULL_LIST_SERIES,
        {"id": 5},
    ),
}


@pytest.fixture
def metron(dummy_api_token: str) -> Session:
    """Return a fresh uncached session against the production URL."""
    return api(dummy_api_token)


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_endpoint_returns_validated_response(
    metron: Session, case: tuple[Callable[[Session], Any], str, str, Any, dict[str, Any]]
) -> None:
    """The endpoint sends one request to its URL and returns the validated response."""
    call, method, path, body, expected = case
    with requests_mock.Mocker() as r:
        r.register_uri(method, f"{BASE_URL}{path}/", json=body)
        result = call(metron)

    assert r.call_count == 1
    item = result[0] if isinstance(result, list) else result
    for attr, value in expected.items():
        assert getattr(item, attr) == value


def test_pull_list_remove_series(metron: Session) -> None:
    """Removing a series sends a DELETE to the entry's remove URL."""
    with requests_mock.Mocker() as r:
        r.delete(f"{BASE_URL}pull_list/series/5/remove/", status_code=204)
        assert metron.pull_list_remove_series(5) is None

    assert r.call_count == 1

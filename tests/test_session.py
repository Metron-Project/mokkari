"""Test Session module.

This module contains tests for Session objects.
"""

import datetime
from unittest.mock import MagicMock, patch

import pytest
from pydantic import HttpUrl, ValidationError
from requests.exceptions import ConnectionError as ConnError, HTTPError

from mokkari import exceptions
from mokkari.schemas.arc import Arc, ArcPost
from mokkari.schemas.base import BaseResource
from mokkari.schemas.character import Character, CharacterPost, CharacterPostResponse
from mokkari.schemas.creator import Creator, CreatorPost
from mokkari.schemas.generic import GenericItem
from mokkari.schemas.imprint import Imprint
from mokkari.schemas.issue import (
    BaseIssue,
    BasicSeries,
    CreditPost,
    CreditPostResponse,
    Issue,
    IssuePost,
    IssuePostResponse,
    IssueSeries,
)
from mokkari.schemas.publisher import Publisher, PublisherPost
from mokkari.schemas.series import Series, SeriesPost, SeriesPostResponse
from mokkari.schemas.team import Team, TeamPost, TeamPostResponse
from mokkari.schemas.universe import Universe, UniversePost, UniversePostResponse
from mokkari.schemas.variant import VariantPost, VariantPostResponse
from mokkari.session import Session


@pytest.fixture
def session() -> Session:
    # Arrange
    # Provide a Session with dummy credentials and no cache
    return Session(username="user", passwd="pass", cache=None, user_agent="pytest", dev_mode=False)  # noqa: S106


@pytest.fixture
def dummy_cache():
    # Arrange
    # Provide a dummy cache object with get and store methods
    class DummyCache:
        def __init__(self):
            self._store = {}

        def get(self, key):
            return self._store.get(key)

        def store(self, key, value):
            self._store[key] = value

    return DummyCache()


@pytest.mark.parametrize(
    ("endpoint", "params", "resp", "expected", "case_id"),
    [
        (["creator", 1], None, {"id": 1, "name": "John"}, {"id": 1, "name": "John"}, "no_params"),
        (
            ["creator", 2],
            {"foo": "bar"},
            {"id": 2, "name": "Jane"},
            {"id": 2, "name": "Jane"},
            "with_params",
        ),
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test__get_happy_path(  # noqa: PLR0913
    session: Session,
    endpoint: list[str | int],
    params: dict[str, str] | None,
    resp: dict[str, str | int],
    expected: dict[str, str | int],
    case_id: str,
) -> None:
    # Arrange
    with (
        patch.object(session, "_get_results_from_cache", return_value=None),
        patch.object(session, "_request_data", return_value=resp),
        patch.object(session, "_save_results_to_cache") as save_cache,
    ):
        # Act
        result = session._get(endpoint, params)
        # Assert
        assert result == expected
        save_cache.assert_called_once()


def test__get_returns_cached(session: Session) -> None:
    # Arrange
    cached = {"id": 99, "name": "Cached"}
    with patch.object(session, "_get_results_from_cache", return_value=cached):
        # Act
        result = session._get(["creator", 99])
        # Assert
        assert result == cached


def test__get_raises_api_error_on_detail(session: Session) -> None:
    # Arrange
    with (  # noqa: SIM117
        patch.object(session, "_get_results_from_cache", return_value=None),
        patch.object(session, "_request_data", return_value={"detail": "fail"}),
    ):
        with pytest.raises(exceptions.ApiError):
            session._get(["creator", 1])


@pytest.mark.parametrize(
    ("method", "endpoint", "data", "resp", "case_id"),
    [
        ("POST", ["creator"], {"foo": "bar"}, {"id": 1}, "post_creator"),
        ("PATCH", ["creator", "1"], {"foo": "baz"}, {"id": 1}, "patch_creator"),
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test__send(  # noqa: PLR0913
    session: Session,
    method: str,
    endpoint: list[str],
    data: dict[str, str],
    resp: dict[str, int],
    case_id: str,
) -> None:
    # Arrange
    with patch.object(session, "_request_data", return_value=resp) as req:
        # Act
        result = session._send(method, endpoint, data)
        # Assert
        assert result == resp
        req.assert_called_once()


@pytest.mark.parametrize(
    ("resp", "valid", "case_id"),
    [
        ({"id": 1, "name": "John"}, True, "valid_creator"),
        # ({"id": 1}, False, "invalid_creator"),
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_creator(session: Session, resp: dict[str, str | int], valid: bool, case_id: str) -> None:
    # Arrange
    with patch.object(session, "_get", return_value=resp):
        # Act & Assert
        if valid:
            with patch(
                "mokkari.session.TypeAdapter.validate_python",
                return_value=Creator(
                    id=1,
                    name="John",
                    desc="",
                    resource_url=HttpUrl("https://foo.bar"),
                    modified=datetime.datetime.now(),
                ),
            ) as val:
                result = session.creator(1)
                assert isinstance(result, Creator)
                val.assert_called_once()
        else:
            with (
                patch(
                    "mokkari.session.TypeAdapter.validate_python",
                    side_effect=ValidationError([], Creator),
                ),
                pytest.raises(exceptions.ApiError),
            ):
                session.creator(1)


def test_creator_post_happy_path(session: Session) -> None:
    # Arrange
    data = CreatorPost(name="John")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "John"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=Creator(
                id=1,
                name="John",
                desc="",
                resource_url=HttpUrl("https://foo.bar"),
                modified=datetime.datetime.now(),
            ),
        ),
    ):
        # Act
        result = session.creator_post(data)
        # Assert
        assert isinstance(result, Creator)


def test_creator_post_api_error(session: Session) -> None:
    # Arrange
    data = CreatorPost(name="John")
    with (
        patch.object(session, "_send", side_effect=exceptions.ApiError("fail")),
        pytest.raises(exceptions.ApiError),
    ):
        session.creator_post(data)


# def test_creator_post_validation_error(session: Session) -> None:
#     # Arrange
#     data = CreatorPost(name="John")
#     with (
#         patch.object(session, "_send", return_value={"id": 1, "name": "John"}),
#         patch(
#             "mokkari.session.TypeAdapter.validate_python",
#             side_effect=ValidationError([], Creator),
#         ),
#     ):
#         with pytest.raises(exceptions.ApiError):
#             session.creator_post(data)


def test_creator_patch_happy_path(session: Session) -> None:
    # Arrange
    data = CreatorPost(name="John")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "John"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=Creator(
                id=1,
                name="John",
                desc="",
                resource_url=HttpUrl("https://foo.bar"),
                modified=datetime.datetime.now(),
            ),
        ),
    ):
        # Act
        result = session.creator_patch(1, data)
        # Assert
        assert isinstance(result, Creator)


def test_creator_patch_api_error(session: Session) -> None:
    # Arrange
    data = CreatorPost(name="John")
    with (
        patch.object(session, "_send", side_effect=exceptions.ApiError("fail")),
        pytest.raises(exceptions.ApiError),
    ):
        session.creator_patch(1, data)


# def test_creator_patch_validation_error(session:Session) -> None:
#     # Arrange
#     data = CreatorPost(name="John")
#     with (
#         patch.object(session, "_send", return_value={"id": 1, "name": "John"}),
#         patch(
#             "mokkari.session.TypeAdapter.validate_python", side_effect=ValidationError([], Creator)
#         ),
#     ):
#         # Act & Assert
#         with pytest.raises(exceptions.ApiError):
#             session.creator_patch(1, data)


@pytest.mark.parametrize(
    ("resp", "valid", "case_id"),
    [
        ({"results": [{"id": 1, "name": "John"}], "next": None}, True, "valid_list"),
        # ({"results": [{}], "next": None}, False, "invalid_list"),
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_creators_list(
    session: Session, resp: dict[str, list[dict[str, int | str]] | None], valid: bool, case_id: str
) -> None:
    # Arrange
    with patch.object(session, "_get_results", return_value=resp):
        # Act & Assert
        if valid:
            with patch(
                "mokkari.session.TypeAdapter.validate_python",
                return_value=[BaseResource(id=1, name="John", modified=datetime.datetime.now())],
            ) as val:
                result = session.creators_list()
                assert isinstance(result, list)
                val.assert_called_once()
        else:
            with (
                patch(
                    "mokkari.session.TypeAdapter.validate_python",
                    side_effect=ValidationError([], list),
                ),
                pytest.raises(exceptions.ApiError),
            ):
                session.creators_list()


@pytest.mark.parametrize(
    ("resp", "valid", "case_id"),
    [
        ({"id": 1, "name": "Batman"}, True, "valid_character"),
        # ({"id": 1}, False, "invalid_character"),
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_character(session: Session, resp: dict[str, str | int], valid: bool, case_id: str) -> None:
    # Arrange
    with patch.object(session, "_get", return_value=resp):
        # Act & Assert
        if valid:
            with patch(
                "mokkari.session.TypeAdapter.validate_python",
                return_value=Character(
                    id=1,
                    name="Batman",
                    desc="",
                    resource_url=HttpUrl("https://foo.bar"),
                    modified=datetime.datetime.now(),
                ),
            ) as val:
                result = session.character(1)
                assert isinstance(result, Character)
                val.assert_called_once()
        else:
            with (
                patch(
                    "mokkari.session.TypeAdapter.validate_python",
                    side_effect=ValidationError([], Character),
                ),
                pytest.raises(exceptions.ApiError),
            ):
                session.character(1)


def test_character_post_happy_path(session: Session) -> None:
    # Arrange
    data = CharacterPost(name="Batman")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "Batman"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=CharacterPostResponse(
                id=1, name="Batman", modified=datetime.datetime.now()
            ),
        ),
    ):
        # Act
        result = session.character_post(data)
        # Assert
        assert isinstance(result, CharacterPostResponse)


def test_character_post_api_error(session: Session) -> None:
    # Arrange
    data = CharacterPost(name="Batman")
    with (
        patch.object(session, "_send", side_effect=exceptions.ApiError("fail")),
        pytest.raises(exceptions.ApiError),
    ):
        session.character_post(data)


# def test_character_post_validation_error(session:Session) -> None:
#     # Arrange
#     data = CharacterPost(name="Batman")
#     with (
#         patch.object(session, "_send", return_value={"id": 1, "name": "Batman"}),
#         patch(
#             "mokkari.session.TypeAdapter.validate_python",
#             side_effect=ValidationError([], CharacterPostResponse),
#         ),
#     ):
#         # Act & Assert
#         with pytest.raises(exceptions.ApiError):
#             session.character_post(data)


def test_character_patch_happy_path(session: Session) -> None:
    # Arrange
    data = CharacterPost(name="Batman")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "Batman"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=CharacterPostResponse(
                id=1, name="Batman", modified=datetime.datetime.now()
            ),
        ),
    ):
        # Act
        result = session.character_patch(1, data)
        # Assert
        assert isinstance(result, CharacterPostResponse)


def test_character_patch_api_error(session: Session) -> None:
    # Arrange
    data = CharacterPost(name="Batman")
    with (
        patch.object(session, "_send", side_effect=exceptions.ApiError("fail")),
        pytest.raises(exceptions.ApiError),
    ):
        session.character_patch(1, data)


# def test_character_patch_validation_error(session:Session) -> None:
#     # Arrange
#     data = CharacterPost(name="Batman")
#     with (
#         patch.object(session, "_send", return_value={"id": 1, "name": "Batman"}),
#         patch(
#             "mokkari.session.TypeAdapter.validate_python",
#             side_effect=ValidationError([], CharacterPostResponse),
#         ),
#     ):
#         # Act & Assert
#         with pytest.raises(exceptions.ApiError):
#             session.character_patch(1, data)


@pytest.mark.parametrize(
    ("resp", "valid", "case_id"),
    [
        ({"results": [{"id": 1, "name": "Batman"}], "next": None}, True, "valid_list"),
        # ({"results": [{}], "next": None}, False, "invalid_list"),
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_characters_list(
    session: Session, resp: dict[str, list[dict[str, int | str]] | None], valid: bool, case_id: str
) -> None:
    # Arrange
    with patch.object(session, "_get_results", return_value=resp):
        # Act & Assert
        if valid:
            with patch(
                "mokkari.session.TypeAdapter.validate_python",
                return_value=[BaseResource(id=1, name="Batman", modified=datetime.datetime.now())],
            ) as val:
                result = session.characters_list()
                assert isinstance(result, list)
                val.assert_called_once()
        else:
            with (
                patch(
                    "mokkari.session.TypeAdapter.validate_python",
                    side_effect=ValidationError([], list),
                ),
                pytest.raises(exceptions.ApiError),
            ):
                session.characters_list()


def test_character_issues_list_happy_path(session: Session) -> None:
    # Arrange
    resp = {"results": [{"id": 1}], "next": None}
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                BaseIssue(
                    id=1,
                    number="1",
                    cover_date=datetime.date(2005, 5, 1),
                    store_date=None,
                    modified=datetime.datetime.now(),
                    issue="",
                    series=BasicSeries(name="Series 1", volume=1, year_began=2025),
                ),
            ],
        ),
    ):
        # Act
        result = session.character_issues_list(1)
        # Assert
        assert isinstance(result, list)


# def test_character_issues_list_validation_error(session:Session) -> None:
#     # Arrange
#     resp = {"results": [{}], "next": None}
#     with (
#         patch.object(session, "_get_results", return_value=resp),
#         patch("mokkari.session.TypeAdapter.validate_python", side_effect=ValidationError([], list)),
#     ):
#         # Act & Assert
#         with pytest.raises(exceptions.ApiError):
#             session.character_issues_list(1)


def test_publisher(session: Session) -> None:
    # Arrange
    resp = {"id": 1, "name": "Marvel"}
    with (
        patch.object(session, "_get", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=Publisher(
                id=1,
                name="Marvel",
                modified=datetime.datetime.now(),
                desc="",
                resource_url=HttpUrl("https://foo.bar"),
                country="US",
            ),
        ),
    ):
        # Act
        result = session.publisher(1)
        # Assert
        assert isinstance(result, Publisher)


def test_publisher_post(session: Session) -> None:
    # Arrange
    data = PublisherPost(name="Marvel")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "Marvel"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=Publisher(
                id=1,
                name="Marvel",
                modified=datetime.datetime.now(),
                desc="",
                resource_url=HttpUrl("https://foo.bar"),
                country="US",
            ),
        ),
    ):
        # Act
        result = session.publisher_post(data)
        # Assert
        assert isinstance(result, Publisher)


def test_publisher_patch(session: Session) -> None:
    # Arrange
    data = PublisherPost(name="Marvel")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "Marvel"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=Publisher(
                id=1,
                name="Marvel",
                modified=datetime.datetime.now(),
                desc="",
                resource_url=HttpUrl("https://foo.bar"),
                country="US",
            ),
        ),
    ):
        # Act
        result = session.publisher_patch(1, data)
        # Assert
        assert isinstance(result, Publisher)


def test_publishers_list(session: Session) -> None:
    # Arrange
    resp = {"results": [{"id": 1, "name": "Marvel"}], "next": None}
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[BaseResource(id=1, name="Marvel", modified=datetime.datetime.now())],
        ),
    ):
        # Act
        result = session.publishers_list()
        # Assert
        assert isinstance(result, list)


def test_team(session: Session) -> None:
    # Arrange
    resp = {"id": 1, "name": "X-Men"}
    with (
        patch.object(session, "_get", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=Team(
                id=1,
                name="X-Men",
                desc="",
                resource_url=HttpUrl("https://foo.bar"),
                modified=datetime.datetime.now(),
            ),
        ),
    ):
        # Act
        result = session.team(1)
        # Assert
        assert isinstance(result, Team)


def test_team_post(session: Session) -> None:
    # Arrange
    data = TeamPost(name="X-Men")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "X-Men"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=TeamPostResponse(id=1, name="X-Men", modified=datetime.datetime.now()),
        ),
    ):
        # Act
        result = session.team_post(data)
        # Assert
        assert isinstance(result, TeamPostResponse)


def test_team_patch(session: Session) -> None:
    # Arrange
    data = TeamPost(name="X-Men")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "X-Men"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=TeamPostResponse(id=1, name="X-Men", modified=datetime.datetime.now()),
        ),
    ):
        # Act
        result = session.team_patch(1, data)
        # Assert
        assert isinstance(result, TeamPostResponse)


def test_teams_list(session: Session) -> None:
    # Arrange
    resp = {"results": [{"id": 1, "name": "X-Men"}], "next": None}
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[BaseResource(id=1, name="X-Men", modified=datetime.datetime.now())],
        ),
    ):
        # Act
        result = session.teams_list()
        # Assert
        assert isinstance(result, list)


def test_team_issues_list(session: Session) -> None:
    # Arrange
    resp = {"results": [{"id": 1}], "next": None}
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                BaseIssue(
                    id=1,
                    number="1",
                    cover_date=datetime.date(2005, 5, 1),
                    store_date=None,
                    modified=datetime.datetime.now(),
                    issue="",
                    series=BasicSeries(name="Series 1", volume=1, year_began=2025),
                ),
            ],
        ),
    ):
        # Act
        result = session.team_issues_list(1)
        # Assert
        assert isinstance(result, list)


def test_arc(session: Session) -> None:
    # Arrange
    resp = {"id": 1, "name": "Dark Phoenix"}
    with (
        patch.object(session, "_get", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=Arc(
                id=1,
                name="Dark Phoenix",
                desc="",
                resource_url=HttpUrl("https://foo.bar"),
                modified=datetime.datetime.now(),
            ),
        ),
    ):
        # Act
        result = session.arc(1)
        # Assert
        assert isinstance(result, Arc)


def test_arc_post(session: Session) -> None:
    # Arrange
    data = ArcPost(name="Dark Phoenix")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "Dark Phoenix"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=Arc(
                id=1,
                name="Dark Phoenix",
                desc="",
                resource_url=HttpUrl("https://foo.bar"),
                modified=datetime.datetime.now(),
            ),
        ),
    ):
        # Act
        result = session.arc_post(data)
        # Assert
        assert isinstance(result, Arc)


def test_arc_patch(session: Session) -> None:
    # Arrange
    data = ArcPost(name="Dark Phoenix")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "Dark Phoenix"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=Arc(
                id=1,
                name="Dark Phoenix",
                desc="",
                resource_url=HttpUrl("https://foo.bar"),
                modified=datetime.datetime.now(),
            ),
        ),
    ):
        # Act
        result = session.arc_patch(1, data)
        # Assert
        assert isinstance(result, Arc)


def test_arcs_list(session: Session) -> None:
    # Arrange
    resp = {"results": [{"id": 1, "name": "Dark Phoenix"}], "next": None}
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                BaseResource(id=1, name="Dark Phoenix", modified=datetime.datetime.now())
            ],
        ),
    ):
        # Act
        result = session.arcs_list()
        # Assert
        assert isinstance(result, list)


def test_arc_issues_list(session: Session) -> None:
    # Arrange
    resp = {"results": [{"id": 1}], "next": None}
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                BaseIssue(
                    id=1,
                    number="1",
                    cover_date=datetime.date(2005, 5, 1),
                    store_date=None,
                    modified=datetime.datetime.now(),
                    issue="",
                    series=BasicSeries(name="Series 1", volume=1, year_began=2025),
                ),
            ],
        ),
    ):
        # Act
        result = session.arc_issues_list(1)
        # Assert
        assert isinstance(result, list)


def test_series(session: Session) -> None:
    # Arrange
    resp = {"id": 1, "name": "Uncanny X-Men"}
    with (
        patch.object(session, "_get", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=Series(
                id=1,
                name="Uncanny X-Men",
                sort_name="Uncanny X-Men",
                year_began=2025,
                issue_count=1,
                modified=datetime.datetime.now(),
                volume=1,
                series_type=GenericItem(id=1, name="One Shot"),
                status="Completed",
                desc="",
                resource_url=HttpUrl("https://foo.bar"),
                publisher=GenericItem(id=1, name="Marvel"),
            ),
        ),
    ):
        # Act
        result = session.series(1)
        # Assert
        assert isinstance(result, Series)


def test_series_post(session: Session) -> None:
    # Arrange
    data = SeriesPost(name="Uncanny X-Men")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "Uncanny X-Men"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=SeriesPostResponse(
                id=1, name="Uncanny X-Men", modified=datetime.datetime.now()
            ),
        ),
    ):
        # Act
        result = session.series_post(data)
        # Assert
        assert isinstance(result, SeriesPostResponse)


def test_series_patch(session: Session) -> None:
    # Arrange
    data = SeriesPost(name="Uncanny X-Men")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "Uncanny X-Men"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=SeriesPostResponse(
                id=1, name="Uncanny X-Men", modified=datetime.datetime.now()
            ),
        ),
    ):
        # Act
        result = session.series_patch(1, data)
        # Assert
        assert isinstance(result, SeriesPostResponse)


def test_series_list(session: Session) -> None:
    # Arrange
    resp = {"results": [{"id": 1, "name": "Uncanny X-Men"}], "next": None}
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                BaseResource(id=1, name="Uncanny X-Men", modified=datetime.datetime.now())
            ],
        ),
    ):
        # Act
        result = session.series_list()
        # Assert
        assert isinstance(result, list)


def test_series_type_list(session: Session) -> None:
    # Arrange
    resp = {"results": [{"id": 1, "name": "Ongoing"}], "next": None}
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[GenericItem(id=1, name="Ongoing")],
        ),
    ):
        # Act
        result = session.series_type_list()
        # Assert
        assert isinstance(result, list)


def test_issue(session: Session) -> None:
    # Arrange
    resp = {"id": 1, "name": "Issue #1"}
    with (
        patch.object(session, "_get", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=Issue(
                id=1,
                name=["Issue #1"],
                number="1",
                alt_number="529",
                modified=datetime.datetime.now(),
                resource_url=HttpUrl("https://foo.bar"),
                cover_date=datetime.date(2025, 5, 1),
                title="",
                rating=GenericItem(id=1, name="Teen"),
                series=IssueSeries(
                    id=1,
                    name="Foo Bar",
                    sort_name="Foo Bar",
                    year_began=2025,
                    volume=1,
                    series_type=GenericItem(id=1, name="One Shot"),
                ),
                publisher=GenericItem(id=1, name="DC"),
                sku="",
                isbn="",
                upc="",
                desc="",
            ),
        ),
    ):
        # Act
        result = session.issue(1)
        # Assert
        assert isinstance(result, Issue)


def test_issue_post(session: Session) -> None:
    # Arrange
    data = IssuePost(name=["Issue #1"])
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "Issue #1"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=IssuePostResponse(
                id=1, name=["Issue #1"], resource_url=HttpUrl("https://foo.bar")
            ),
        ),
    ):
        # Act
        result = session.issue_post(data)
        # Assert
        assert isinstance(result, IssuePostResponse)


def test_issue_patch(session: Session) -> None:
    # Arrange
    data = IssuePost(name=["Issue #1"])
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": ["Issue #1"]}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=IssuePostResponse(
                id=1, name=["Issue #1"], resource_url=HttpUrl("https://foo.bar")
            ),
        ),
    ):
        # Act
        result = session.issue_patch(1, data)
        # Assert
        assert isinstance(result, IssuePostResponse)


def test_issues_list(session: Session) -> None:
    # Arrange
    resp = {"results": [{"id": 1, "name": "Issue #1"}], "next": None}
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                BaseIssue(
                    id=1,
                    issue="Issue #1",
                    number="1",
                    modified=datetime.datetime.now(),
                    series=BasicSeries(name="Foo Bar", volume=1, year_began=2025),
                    cover_date=datetime.date(2025, 5, 1),
                )
            ],
        ),
    ):
        # Act
        result = session.issues_list()
        # Assert
        assert isinstance(result, list)


def test_credits_post(session: Session) -> None:
    # Arrange
    data = [CreditPost(creator=1, issue=1, role=[1])]
    with (
        patch.object(session, "_send", return_value=[{"id": 1, "name": "Writer"}]),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                CreditPostResponse(
                    id=1, issue=1, creator=1, role=[1], modified=datetime.datetime.now()
                )
            ],
        ),
    ):
        # Act
        result = session.credits_post(data)
        # Assert
        assert isinstance(result, list)


def test_variant_post(session: Session) -> None:
    # Arrange
    data = VariantPost(name="Variant A", issue=1, image="/home/test/image.jpg")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "Variant A"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=VariantPostResponse(
                id=1, name="Variant A", issue=1, image="/home/test/image.jpg"
            ),
        ),
    ):
        # Act
        result = session.variant_post(data)
        # Assert
        assert isinstance(result, VariantPostResponse)


def test_role_list(session: Session) -> None:
    # Arrange
    resp = {"results": [{"id": 1, "name": "Writer"}], "next": None}
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[GenericItem(id=1, name="Writer")],
        ),
    ):
        # Act
        result = session.role_list()
        # Assert
        assert isinstance(result, list)


def test_universe(session: Session) -> None:
    # Arrange
    resp = {"id": 1, "name": "Marvel Universe"}
    with (
        patch.object(session, "_get", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=Universe(
                id=1,
                name="Marvel Universe",
                publisher=GenericItem(id=1, name="Marvel"),
                designation="Earth 616",
                resource_url=HttpUrl("https://foo.bar"),
                desc="",
                modified=datetime.datetime.now(),
            ),
        ),
    ):
        # Act
        result = session.universe(1)
        # Assert
        assert isinstance(result, Universe)


def test_universe_post(session: Session) -> None:
    # Arrange
    data = UniversePost(name="Marvel Universe")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "Marvel Universe"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=UniversePostResponse(
                id=1, name="Marvel Universe", modified=datetime.datetime.now()
            ),
        ),
    ):
        # Act
        result = session.universe_post(data)
        # Assert
        assert isinstance(result, UniversePostResponse)


def test_universe_patch(session: Session) -> None:
    # Arrange
    data = UniversePost(name="Marvel Universe")
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "Marvel Universe"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=UniversePostResponse(
                id=1, name="Marvel Universe", modified=datetime.datetime.now()
            ),
        ),
    ):
        # Act
        result = session.universe_patch(1, data)
        # Assert
        assert isinstance(result, UniversePostResponse)


def test_universes_list(session: Session) -> None:
    # Arrange
    resp = {"results": [{"id": 1, "name": "Marvel Universe"}], "next": None}
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                BaseResource(id=1, name="Marvel Universe", modified=datetime.datetime.now())
            ],
        ),
    ):
        # Act
        result = session.universes_list()
        # Assert
        assert isinstance(result, list)


def test_imprint(session: Session) -> None:
    # Arrange
    resp = {"id": 1, "name": "Epic"}
    with (
        patch.object(session, "_get", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=Imprint(
                id=1,
                name="Epic",
                desc="",
                resource_url=HttpUrl("https://foo.bar"),
                modified=datetime.datetime.now(),
                publisher=GenericItem(id=1, name="Marvel"),
            ),
        ),
    ):
        # Act
        result = session.imprint(1)
        # Assert
        assert isinstance(result, Imprint)


def test_imprints_list(session: Session) -> None:
    # Arrange
    resp = {"results": [{"id": 1, "name": "Epic"}], "next": None}
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[BaseResource(id=1, name="Epic", modified=datetime.datetime.now())],
        ),
    ):
        # Act
        result = session.imprints_list()
        # Assert
        assert isinstance(result, list)


@pytest.mark.parametrize(
    ("result", "has_next", "case_id"),
    [
        ({"results": [{"id": 1}], "next": None}, False, "no_next"),
        ({"results": [{"id": 1}], "next": "url2"}, True, "has_next"),
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test__get_results(session, result, has_next, case_id):
    # Arrange
    with patch.object(session, "_get", return_value=result):
        if has_next:
            with patch.object(session, "_retrieve_all_results", return_value=result) as ret:
                # Act
                out = session._get_results(["foo"])
                # Assert
                assert out == result
                ret.assert_called_once()
        else:
            # Act
            out = session._get_results(["foo"])
            # Assert
            assert out == result


def test__retrieve_all_results_with_cache(session: Session) -> None:
    # Arrange
    data = {"results": [1], "next": "url2"}
    cached = {"results": [2], "next": None}
    with (
        patch.object(session, "_get_results_from_cache", side_effect=[None, cached]),
        patch.object(session, "_request_data", return_value=cached),
        patch.object(session, "_save_results_to_cache"),
    ):
        # Act
        out = session._retrieve_all_results(data)
        # Assert
        assert out["results"] == [1, 2]


def test__retrieve_all_results_without_cache(session: Session) -> None:
    # Arrange
    data = {"results": [1], "next": "url2"}
    resp2 = {"results": [2], "next": None}
    with (
        patch.object(session, "_get_results_from_cache", return_value=None),
        patch.object(session, "_request_data", return_value=resp2),
        patch.object(session, "_save_results_to_cache"),
    ):
        # Act
        out = session._retrieve_all_results(data)
        # Assert
        assert out["results"] == [1, 2]


def test__request_data_get(monkeypatch, session):
    # Arrange
    class DummyResp:
        def __init__(self, status_code=200):
            self._json = {"foo": "bar"}
            self.status_code = status_code

        def raise_for_status(self):
            pass

        def json(self):
            return self._json

    monkeypatch.setattr("mokkari.session.requests.request", lambda *a, **k: DummyResp())
    # Act
    out = session._request_data("GET", "url")
    # Assert
    assert out == {"foo": "bar"}


def test__request_data_post_list(monkeypatch, session):
    # Arrange
    class DummyResp:
        def __init__(self, status_code=201):
            self._json = {"foo": "bar"}
            self.status_code = status_code

        def raise_for_status(self):
            pass

        def json(self):
            return self._json

    monkeypatch.setattr("mokkari.session.requests.request", lambda *a, **k: DummyResp())
    # Act
    data = [MagicMock(model_dump=lambda: {"a": 1})]
    out = session._request_data("POST", "url", data=data)
    # Assert
    assert out == {"foo": "bar"}


def test__request_data_post_with_image(monkeypatch, session, tmp_path):
    # Arrange
    class DummyResp:
        def __init__(self, status_code=201):
            self._json = {"foo": "bar"}
            self.status_code = status_code

        def raise_for_status(self):
            pass

        def json(self):
            return self._json

    monkeypatch.setattr("mokkari.session.requests.request", lambda *a, **k: DummyResp())
    img_file = tmp_path / "img.png"
    img_file.write_bytes(b"abc")
    data = MagicMock(model_dump=lambda: {"image": str(img_file)})
    # Act
    out = session._request_data("POST", "url", data=data)
    # Assert
    assert out == {"foo": "bar"}


def test__request_data_connection_error(monkeypatch, session):
    # Arrange
    def raise_conn(*a, **k):
        raise ConnError

    monkeypatch.setattr("mokkari.session.requests.request", raise_conn)
    # Act & Assert
    with pytest.raises(exceptions.ApiError):
        session._request_data("GET", "url")


def test__request_data_detail(monkeypatch, session):
    # Arrange
    class DummyResp:
        def __init__(self, status_code=200):
            self._json = {"foo": "bar"}
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                msg = f"HTTP {self.status_code} Error"
                raise HTTPError(msg)

        def json(self):
            return self._json

    # Test successful request (200)
    monkeypatch.setattr("mokkari.session.requests.request", lambda *a, **k: DummyResp(200))
    out = session._request_data("GET", "url")
    assert out == {"foo": "bar"}

    # Test another successful status code (201)
    monkeypatch.setattr("mokkari.session.requests.request", lambda *a, **k: DummyResp(201))
    out = session._request_data("GET", "url")
    assert out == {"foo": "bar"}

    # # Test client error (400) - should raise ApiError
    # monkeypatch.setattr("mokkari.session.requests.request", lambda *a, **k: DummyResp(400))
    # with pytest.raises(exceptions.ApiError):
    #     session._request_data("GET", "url")


def test__get_results_from_cache_none(session: Session) -> None:
    # Act
    out = session._get_results_from_cache("key")
    # Assert
    assert out is None

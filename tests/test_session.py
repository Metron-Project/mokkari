"""Test Session module.

This module contains tests for Session objects.
"""

import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from pydantic import HttpUrl, ValidationError
from pyrate_limiter import Duration, Rate
from pyrate_limiter.abstracts.rate import RateItem
from pyrate_limiter.exceptions import BucketFullException, LimiterDelayException
from requests.exceptions import ConnectionError as ConnError, HTTPError

from mokkari import exceptions
from mokkari.schemas.arc import Arc, ArcPost
from mokkari.schemas.base import BaseResource
from mokkari.schemas.character import Character, CharacterPost, CharacterPostResponse
from mokkari.schemas.collection import (
    CollectionFormatStat,
    CollectionIssue,
    CollectionList,
    CollectionRead,
    CollectionStats,
    MissingIssue,
    MissingSeries,
)
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
from mokkari.schemas.reading_list import (
    AttributionSource,
    ReadingListIssue,
    ReadingListItem,
    ReadingListList,
    ReadingListRead,
)
from mokkari.schemas.series import Series, SeriesPost, SeriesPostResponse
from mokkari.schemas.team import Team, TeamPost, TeamPostResponse
from mokkari.schemas.universe import Universe, UniversePost, UniversePostResponse
from mokkari.schemas.user import User
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
                price=None,
                price_currency="",
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
    data = VariantPost(
        name="Variant A", issue=1, image="/home/test/image.jpg", price=Decimal("3.99")
    )
    with (
        patch.object(session, "_send", return_value={"id": 1, "name": "Variant A"}),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=VariantPostResponse(
                id=1,
                name="Variant A",
                issue=1,
                image="/home/test/image.jpg",
                price=Decimal("3.99"),
                price_currency="USD",
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


def test_reading_list(session: Session) -> None:
    # Arrange
    resp = {
        "id": 1,
        "name": "My Reading List",
        "slug": "my-reading-list",
        "user": {"id": 1, "username": "testuser"},
        "desc": "A test reading list",
        "is_private": False,
        "attribution_source": "CBRO",
        "attribution_url": "https://example.com/list",
        "average_rating": 4.5,
        "rating_count": 10,
        "items_url": "https://api.example.com/reading_list/1/items/",
        "resource_url": "https://api.example.com/reading_list/1/",
        "modified": "2023-01-01T12:00:00Z",
    }
    with (
        patch.object(session, "_get", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=ReadingListRead(
                id=1,
                name="My Reading List",
                slug="my-reading-list",
                user=User(id=1, username="testuser"),
                desc="A test reading list",
                is_private=False,
                attribution_source="CBRO",
                attribution_url=HttpUrl("https://example.com/list"),
                average_rating=4.5,
                rating_count=10,
                items_url="https://api.example.com/reading_list/1/items/",
                resource_url="https://api.example.com/reading_list/1/",
                modified=datetime.datetime.now(),
            ),
        ),
    ):
        # Act
        result = session.reading_list(1)
        # Assert
        assert isinstance(result, ReadingListRead)
        assert result.name == "My Reading List"


def test_reading_lists_list(session: Session) -> None:
    # Arrange
    resp = {
        "results": [
            {
                "id": 1,
                "name": "My Reading List",
                "slug": "my-reading-list",
                "user": {"id": 1, "username": "testuser"},
                "is_private": False,
                "attribution_source": AttributionSource.CBRO,
                "average_rating": 4.5,
                "rating_count": 10,
                "modified": "2023-01-01T12:00:00Z",
            }
        ],
        "next": None,
    }
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                ReadingListList(
                    id=1,
                    name="My Reading List",
                    slug="my-reading-list",
                    user=User(id=1, username="testuser"),
                    is_private=False,
                    attribution_source=AttributionSource.CBRO,
                    average_rating=4.5,
                    rating_count=10,
                    modified=datetime.datetime.now(),
                )
            ],
        ),
    ):
        # Act
        result = session.reading_lists_list()
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].name == "My Reading List"


def test_reading_lists_list_with_params(session: Session) -> None:
    # Arrange
    params = {"username": "testuser", "is_private": False}
    resp = {
        "results": [
            {
                "id": 1,
                "name": "Public List",
                "slug": "public-list",
                "user": {"id": 1, "username": "testuser"},
                "is_private": False,
                "average_rating": 4.5,
                "rating_count": 10,
                "modified": "2023-01-01T12:00:00Z",
            }
        ],
        "next": None,
    }
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                ReadingListList(
                    id=1,
                    name="Public List",
                    slug="public-list",
                    user=User(id=1, username="testuser"),
                    is_private=False,
                    average_rating=4.5,
                    rating_count=10,
                    modified=datetime.datetime.now(),
                )
            ],
        ),
    ):
        # Act
        result = session.reading_lists_list(params)
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1


def test_reading_list_items(session: Session) -> None:
    # Arrange
    resp = {
        "results": [
            {
                "id": 1,
                "issue": {
                    "id": 100,
                    "series": {"name": "Batman", "volume": 1, "year_began": 1940},
                    "number": "1",
                    "cover_date": "2023-01-01",
                    "modified": "2023-01-01T12:00:00Z",
                },
                "order": 1,
            }
        ],
        "next": None,
    }
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                ReadingListItem(
                    id=1,
                    issue=ReadingListIssue(
                        id=100,
                        series=BasicSeries(name="Batman", volume=1, year_began=1940),
                        number="1",
                        cover_date=datetime.date(2023, 1, 1),
                        modified=datetime.datetime.now(),
                    ),
                    order=1,
                    issue_type="Core Issue",
                )
            ],
        ),
    ):
        # Act
        result = session.reading_list_items(1)
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].order == 1
        assert result[0].issue.number == "1"


def test_collection(session: Session) -> None:
    # Arrange
    resp = {
        "id": 1,
        "user": {"id": 1, "username": "testuser"},
        "issue": {
            "id": 100,
            "series": {"name": "Batman", "volume": 1, "year_began": 1940},
            "number": "1",
            "cover_date": "2023-01-01",
            "modified": "2023-01-01T12:00:00Z",
        },
        "quantity": 1,
        "book_format": "PRINT",
        "grade": 9.8,
        "grading_company": "CGC",
        "purchase_date": "2023-01-15",
        "purchase_price": "49.99",
        "purchase_store": "Local Comic Shop",
        "storage_location": "Box 1",
        "notes": "First appearance",
        "is_read": True,
        "date_read": "2023-01-20",
        "rating": 5,
        "resource_url": "https://api.example.com/collection/1/",
        "created_on": "2023-01-01T10:00:00Z",
        "modified": "2023-01-01T12:00:00Z",
    }
    with (
        patch.object(session, "_get", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=CollectionRead(
                id=1,
                user=User(id=1, username="testuser"),
                issue=CollectionIssue(
                    id=100,
                    series=BasicSeries(name="Batman", volume=1, year_began=1940),
                    number="1",
                    cover_date=datetime.date(2023, 1, 1),
                    modified=datetime.datetime.now(),
                ),
                quantity=1,
                book_format="PRINT",
                grade=9.8,
                grading_company="CGC",
                purchase_date=datetime.date(2023, 1, 15),
                purchase_price=Decimal("49.99"),
                purchase_store="Local Comic Shop",
                storage_location="Box 1",
                notes="First appearance",
                is_read=True,
                date_read=datetime.date(2023, 1, 20),
                rating=5,
                resource_url="https://api.example.com/collection/1/",
                created_on=datetime.datetime.now(),
                modified=datetime.datetime.now(),
            ),
        ),
    ):
        # Act
        result = session.collection(1)
        # Assert
        assert isinstance(result, CollectionRead)
        assert result.id == 1
        assert result.book_format == "PRINT"


def test_collections_list(session: Session) -> None:
    # Arrange
    resp = {
        "results": [
            {
                "id": 1,
                "user": {"id": 1, "username": "testuser"},
                "issue": {
                    "id": 100,
                    "series": {"name": "Batman", "volume": 1, "year_began": 1940},
                    "number": "1",
                    "cover_date": "2023-01-01",
                    "modified": "2023-01-01T12:00:00Z",
                },
                "quantity": 1,
                "book_format": "PRINT",
                "grading_company": "CGC",
                "is_read": True,
                "modified": "2023-01-01T12:00:00Z",
            }
        ],
        "next": None,
    }
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                CollectionList(
                    id=1,
                    user=User(id=1, username="testuser"),
                    issue=CollectionIssue(
                        id=100,
                        series=BasicSeries(name="Batman", volume=1, year_began=1940),
                        number="1",
                        cover_date=datetime.date(2023, 1, 1),
                        modified=datetime.datetime.now(),
                    ),
                    quantity=1,
                    book_format="PRINT",
                    grading_company="CGC",
                    is_read=True,
                    modified=datetime.datetime.now(),
                )
            ],
        ),
    ):
        # Act
        result = session.collections_list()
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].book_format == "PRINT"


def test_collections_list_with_params(session: Session) -> None:
    # Arrange
    params = {"is_read": False, "book_format": "DIGITAL"}
    resp = {
        "results": [
            {
                "id": 2,
                "user": {"id": 1, "username": "testuser"},
                "issue": {
                    "id": 101,
                    "series": {"name": "Superman", "volume": 1, "year_began": 1938},
                    "number": "1",
                    "cover_date": "2023-02-01",
                    "modified": "2023-02-01T12:00:00Z",
                },
                "quantity": 1,
                "book_format": "DIGITAL",
                "grading_company": "",
                "is_read": False,
                "modified": "2023-02-01T12:00:00Z",
            }
        ],
        "next": None,
    }
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                CollectionList(
                    id=2,
                    user=User(id=1, username="testuser"),
                    issue=CollectionIssue(
                        id=101,
                        series=BasicSeries(name="Superman", volume=1, year_began=1938),
                        number="1",
                        cover_date=datetime.date(2023, 2, 1),
                        modified=datetime.datetime.now(),
                    ),
                    quantity=1,
                    book_format="DIGITAL",
                    grading_company="",
                    is_read=False,
                    modified=datetime.datetime.now(),
                )
            ],
        ),
    ):
        # Act
        result = session.collections_list(params)
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].book_format == "DIGITAL"
        assert result[0].is_read is False


def test_collection_missing_issues(session: Session) -> None:
    # Arrange
    resp = {
        "results": [
            {
                "id": 200,
                "series": {"name": "Batman", "volume": 1, "year_began": 1940},
                "number": "2",
                "cover_date": "2023-02-01",
                "store_date": "2023-01-15",
            },
            {
                "id": 201,
                "series": {"name": "Batman", "volume": 1, "year_began": 1940},
                "number": "3",
                "cover_date": "2023-03-01",
            },
        ],
        "next": None,
    }
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                MissingIssue(
                    id=200,
                    series=BasicSeries(name="Batman", volume=1, year_began=1940),
                    number="2",
                    cover_date=datetime.date(2023, 2, 1),
                    store_date=datetime.date(2023, 1, 15),
                ),
                MissingIssue(
                    id=201,
                    series=BasicSeries(name="Batman", volume=1, year_began=1940),
                    number="3",
                    cover_date=datetime.date(2023, 3, 1),
                ),
            ],
        ),
    ):
        # Act
        result = session.collection_missing_issues(1)
        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].number == "2"
        assert result[1].number == "3"


def test_collection_missing_series(session: Session) -> None:
    # Arrange
    resp = {
        "results": [
            {
                "id": 1,
                "name": "Batman",
                "sort_name": "Batman",
                "year_began": 1940,
                "year_end": 2011,
            },
            {
                "id": 2,
                "name": "Superman",
                "sort_name": "Superman",
                "year_began": 1938,
            },
        ],
        "next": None,
    }
    with (
        patch.object(session, "_get_results", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=[
                MissingSeries(
                    id=1,
                    name="Batman",
                    sort_name="Batman",
                    year_began=1940,
                    year_end=2011,
                ),
                MissingSeries(
                    id=2,
                    name="Superman",
                    sort_name="Superman",
                    year_began=1938,
                ),
            ],
        ),
    ):
        # Act
        result = session.collection_missing_series()
        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].name == "Batman"
        assert result[1].name == "Superman"


def test_collection_stats(session: Session) -> None:
    # Arrange
    resp = {
        "total_items": 200,
        "total_quantity": 250,
        "total_value": "5000.00",
        "read_count": 150,
        "unread_count": 50,
        "by_format": [
            {"book_format": "PRINT", "count": 180},
            {"book_format": "DIGITAL", "count": 20},
        ],
    }
    with (
        patch.object(session, "_get", return_value=resp),
        patch(
            "mokkari.session.TypeAdapter.validate_python",
            return_value=CollectionStats(
                total_items=200,
                total_quantity=250,
                total_value="5000.00",
                read_count=150,
                unread_count=50,
                by_format=[
                    CollectionFormatStat(book_format="PRINT", count=180),
                    CollectionFormatStat(book_format="DIGITAL", count=20),
                ],
            ),
        ),
    ):
        # Act
        result = session.collection_stats()
        # Assert
        assert isinstance(result, CollectionStats)
        assert result.total_items == 200
        assert result.total_quantity == 250
        assert result.read_count == 150
        assert result.unread_count == 50
        assert len(result.by_format) == 2


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


# ============================================================================
# Rate Limiting Tests
# ============================================================================


def test_rate_limit_minute_exceeded(session: Session) -> None:
    """Test that minute rate limit raises RateLimitError with correct message."""
    # Arrange
    # Create exception that simulates minute rate limit (60 seconds = 1 minute)
    rate_item = RateItem("metron", 1)
    rate = Rate(30, Duration.MINUTE)
    exc = LimiterDelayException(rate_item, rate, actual_delay=60000, max_delay=0)

    with patch.object(session._limiter, "try_acquire", side_effect=exc):
        # Act & Assert
        with pytest.raises(exceptions.RateLimitError) as excinfo:
            session._request_data("GET", "https://test.com/api/issue/1")

        # Verify error message content
        error_msg = str(excinfo.value)
        assert "Rate limit exceeded" in error_msg
        assert "30 requests per minute" in error_msg
        assert "Please wait" in error_msg
        assert "1 minute" in error_msg

        # Verify retry_after attribute is set correctly (60000 ms = 60 seconds)
        assert excinfo.value.retry_after == 60.0


def test_rate_limit_day_exceeded(session: Session) -> None:
    """Test that daily rate limit raises RateLimitError with correct message."""
    # Arrange
    # Create exception that simulates daily rate limit (24 hours = 86400 seconds)
    rate_item = RateItem("metron", 1)
    rate = Rate(10000, Duration.DAY)
    exc = LimiterDelayException(rate_item, rate, actual_delay=86400000, max_delay=0)

    with patch.object(session._limiter, "try_acquire", side_effect=exc):
        # Act & Assert
        with pytest.raises(exceptions.RateLimitError) as excinfo:
            session._request_data("GET", "https://test.com/api/issue/1")

        # Verify error message content
        error_msg = str(excinfo.value)
        assert "Rate limit exceeded" in error_msg
        assert "10,000 requests per day" in error_msg
        assert "Please wait" in error_msg
        assert "24 hours" in error_msg

        # Verify retry_after attribute is set correctly (86400000 ms = 86400 seconds)
        assert excinfo.value.retry_after == 86400.0


def test_rate_limit_blocks_request(session: Session, monkeypatch) -> None:
    """Test that rate limit prevents HTTP request from being made."""
    # Arrange
    rate_item = RateItem("metron", 1)
    rate = Rate(30, Duration.MINUTE)
    exc = LimiterDelayException(rate_item, rate, actual_delay=60000, max_delay=0)

    # Mock HTTP request to track if it's called
    mock_request_called = {"called": False}

    def mock_request(*args, **kwargs):
        mock_request_called["called"] = True
        return MagicMock()

    monkeypatch.setattr("mokkari.session.requests.request", mock_request)

    with patch.object(session._limiter, "try_acquire", side_effect=exc):
        # Act & Assert
        with pytest.raises(exceptions.RateLimitError):
            session._request_data("GET", "https://test.com/api/issue/1")

        # Verify HTTP request was NOT made
        assert not mock_request_called["called"], (
            "HTTP request should not be made when rate limited"
        )


def test_rate_limit_bucket_full_exception(session: Session) -> None:
    """Test handling of BucketFullException from pyrate-limiter."""
    # Arrange
    # Create BucketFullException
    rate_item = RateItem("metron", 1)
    rate = Rate(30, Duration.MINUTE)
    exc = BucketFullException(rate_item, rate)
    # Manually set remaining_time in meta_info
    exc.meta_info["remaining_time"] = 90.5

    with patch.object(session._limiter, "try_acquire", side_effect=exc):
        # Act & Assert
        with pytest.raises(exceptions.RateLimitError) as excinfo:
            session._request_data("GET", "https://test.com/api/issue/1")

        # Verify error message is formatted correctly
        error_msg = str(excinfo.value)
        assert "Rate limit exceeded" in error_msg
        assert "30 requests per minute" in error_msg
        assert "1 minute, 30 seconds" in error_msg


def test_rate_limit_format_time_hours(session: Session) -> None:
    """Test that rate limit error message correctly formats hours."""
    # Arrange
    # Create exception with 2.5 hours delay (9000 seconds = 2h 30m)
    rate_item = RateItem("metron", 1)
    rate = Rate(10000, Duration.DAY)
    exc = LimiterDelayException(rate_item, rate, actual_delay=9000000, max_delay=0)

    with patch.object(session._limiter, "try_acquire", side_effect=exc):
        # Act & Assert
        with pytest.raises(exceptions.RateLimitError) as excinfo:
            session._request_data("GET", "https://test.com/api/issue/1")

        # Verify time formatting
        error_msg = str(excinfo.value)
        assert "2 hours, 30 minutes" in error_msg


def test_rate_limit_allows_successful_request(session: Session, monkeypatch) -> None:
    """Test that requests proceed normally when rate limit is not exceeded."""

    # Arrange
    class DummyResp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"id": 1, "name": "Test"}

    monkeypatch.setattr("mokkari.session.requests.request", lambda *a, **k: DummyResp())

    # Mock limiter to allow request (no exception)
    with patch.object(session._limiter, "try_acquire", return_value=None):
        # Act
        result = session._request_data("GET", "https://test.com/api/issue/1")

        # Assert
        assert result == {"id": 1, "name": "Test"}

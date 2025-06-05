# ruff: noqa: TRY003, EM102
"""Session module.

This module provides the following classes:

- Session
"""

from __future__ import annotations

__all__ = ["Session"]

import json
import logging
import platform
from collections import OrderedDict
from pathlib import Path
from typing import Any, ClassVar, TypeVar
from urllib.parse import urlencode

import requests
from pydantic import TypeAdapter, ValidationError
from pyrate_limiter import Duration, Limiter, Rate, SQLiteBucket

from mokkari import __version__, exceptions, sqlite_cache
from mokkari.exceptions import ApiError
from mokkari.schemas.arc import Arc, ArcPost
from mokkari.schemas.base import BaseResource
from mokkari.schemas.character import Character, CharacterPost, CharacterPostResponse
from mokkari.schemas.creator import Creator, CreatorPost
from mokkari.schemas.generic import GenericItem
from mokkari.schemas.imprint import Imprint
from mokkari.schemas.issue import (
    BaseIssue,
    CreditPost,
    CreditPostResponse,
    Issue,
    IssuePost,
    IssuePostResponse,
)
from mokkari.schemas.publisher import Publisher, PublisherPost
from mokkari.schemas.series import BaseSeries, Series, SeriesPost, SeriesPostResponse
from mokkari.schemas.team import Team, TeamPost, TeamPostResponse
from mokkari.schemas.universe import Universe, UniversePost, UniversePostResponse
from mokkari.schemas.variant import VariantPost, VariantPostResponse

LOGGER = logging.getLogger(__name__)

METRON_MINUTE_RATE_LIMIT = 30
METRON_DAY_RATE_LIMIT = 10_000
METRON_URL = "https://metron.cloud/api/{}/"
LOCAL_URL = "http://127.0.0.1:8000/api/{}/"


def rate_mapping(*args: any, **kwargs: any) -> tuple[str, int]:  # NOQA: ARG001
    return "metron", 1


class Session:
    """A class representing a Session for interacting with the API.

    Args:
        username: A string representing the username for authentication.
        passwd: A string representing the password for authentication.
        cache: An optional SqliteCache object for caching data.
        user_agent: An optional string representing the user agent for the session.
        dev_mode: A boolean indicating whether the session should be run against a local Metron instance.
    """

    _minute_rate = Rate(METRON_MINUTE_RATE_LIMIT, Duration.MINUTE)
    _day_rate = Rate(METRON_DAY_RATE_LIMIT, Duration.DAY)
    _rates: ClassVar[list[Rate]] = [_minute_rate, _day_rate]
    _bucket = SQLiteBucket.init_from_file(_rates)
    _limiter = Limiter(_bucket, raise_when_fail=False, max_delay=Duration.DAY)
    decorator = _limiter.as_decorator()

    T = TypeVar(
        "T",
        ArcPost,
        CharacterPost,
        CreatorPost,
        list[CreditPost],
        VariantPost,
        IssuePost,
        PublisherPost,
        SeriesPost,
        TeamPost,
        UniversePost,
    )

    def __init__(
        self: Session,
        username: str,
        passwd: str,
        cache: sqlite_cache.SqliteCache | None = None,
        user_agent: str | None = None,
        dev_mode: bool = False,
    ) -> None:
        """Initialize a Session object with the provided username, password, cache, and user agent."""
        self.username = username
        self.passwd = passwd
        self.header = {
            "User-Agent": f"{f'{user_agent} ' if user_agent is not None else ''}"
            f"Mokkari/{__version__} ({platform.system()}; {platform.release()})"
        }
        self.api_url = LOCAL_URL if dev_mode else METRON_URL
        self.cache = cache

    def _get(
        self: Session,
        endpoint: list[str | int],
        params: dict[str, str | int] | None = None,
    ) -> dict[str, Any]:
        """Send a request to the specified endpoint with optional parameters.

        Args:
            endpoint: A list of strings or integers representing the endpoint path.
            params: A dictionary of parameters to be included in the request URL.

        Returns:
            A dictionary containing the response data from the API.

        Raises:
            ApiError: If the response data contains a 'detail' key indicating an error.
        """
        if params is None:
            params = {}

        cache_params = ""
        if params:
            ordered_params = OrderedDict(sorted(params.items(), key=lambda t: t[0]))
            cache_params = f"?{urlencode(ordered_params)}"

        url = self.api_url.format("/".join(str(e) for e in endpoint))
        cache_key = f"{url}{cache_params}"

        cached_response = self._get_results_from_cache(cache_key)
        if cached_response is not None:
            return cached_response

        data = self._request_data("GET", url, params)

        if "detail" in data:
            raise exceptions.ApiError(data["detail"])

        self._save_results_to_cache(cache_key, data)

        return data

    def _send(self: Session, method: str, endpoint: list[str], data: T) -> any:
        """Send a request to the specified endpoint with the given data.

        Args:
            method: The HTTP method for the request.
            endpoint: A list of strings representing the endpoint path.
            data: The data to be sent with the request.

        Returns:
            The response data from the API.

        Raises:
            ApiError: If there is an error during the API call.
        """
        url = self.api_url.format("/".join(str(e) for e in endpoint))
        return self._request_data(method=method, url=url, data=data)

    def creator(self: Session, _id: int) -> Creator:
        """Retrieve information about a creator with the specified ID.

        Args:
            _id: An integer representing the ID of the creator.

        Returns:
            A Creator object containing information about the specified creator.

        Raises:
            ValidationError: If there is an error validating the response data.
        """
        resp = self._get(["creator", _id])
        adaptor = TypeAdapter(Creator)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def creator_post(self: Session, data: CreatorPost) -> Creator:
        """Create a new creator.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            data: CreatorPost object with the creator data.

        Returns:
            A Creator object containing information about the created creator.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("POST", ["creator"], data)
        except exceptions.ApiError as error:
            raise exceptions.ApiError(error) from error

        adaptor = TypeAdapter(Creator)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def creator_patch(self: Session, _id: int, data: CreatorPost) -> Creator:
        """Update an existing creator.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            _id: The ID of the creator to update.
            data: CreatorPost object with the updated creator data.

        Returns:
            A Creator object containing information about the updated creator.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("PATCH", ["creator", _id], data)
        except exceptions.ApiError as error:
            raise exceptions.ApiError(error) from error

        adaptor = TypeAdapter(Creator)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def creators_list(
        self: Session, params: dict[str, str | int] | None = None
    ) -> list[BaseResource]:
        """Retrieve a list of creators based on the provided parameters.

        Args:
            params: An optional dictionary of parameters for filtering the list of creators.

        Returns:
            A list of BaseResource objects representing the creators that match the criteria.

        Raises:
            ApiError: If there is an error in the API response data validation.

        """
        resp = self._get_results(["creator"], params)
        adaptor = TypeAdapter(list[BaseResource])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def character(self: Session, _id: int) -> Character:
        """Retrieve information about a character with the specified ID.

        Args:
            _id: An integer representing the ID of the character.

        Returns:
            A Character object containing information about the specified character.

        Raises:
            ApiError: If there is an error in the API response data validation.

        """
        resp = self._get(["character", _id])
        adaptor = TypeAdapter(Character)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def character_post(self: Session, data: CharacterPost) -> CharacterPostResponse:
        """Create a new character.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            data: CharacterPost object with the character data.

        Returns:
            A Character object containing information about the created character.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("POST", ["character"], data)
        except exceptions.ApiError as error:
            raise exceptions.ApiError(error) from error

        adaptor = TypeAdapter(CharacterPostResponse)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def character_patch(self: Session, _id: int, data: CharacterPost) -> CharacterPostResponse:
        """Update an existing character.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            _id: The ID of the character to update.
            data: CharacterPost object with the updated character data.

        Returns:
            A CharacterPostResponse object containing information about the updated character.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("PATCH", ["character", _id], data)
        except exceptions.ApiError as error:
            raise exceptions.ApiError(error) from error

        adaptor = TypeAdapter(CharacterPostResponse)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def characters_list(
        self: Session, params: dict[str, str | int] | None = None
    ) -> list[BaseResource]:
        """Retrieve a list of characters based on the provided parameters.

        Args:
            params: An optional dictionary of parameters for filtering the list of characters.

        Returns:
            A list of BaseResource objects representing the characters that match the criteria.

        Raises:
            ApiError: If there is an error in the API response data validation.

        """
        resp = self._get_results(["character"], params)
        adaptor = TypeAdapter(list[BaseResource])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def character_issues_list(self: Session, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues related to a character with the specified ID.

        Args:
            _id: An integer representing the ID of the character.

        Returns:
            A list of BaseIssue objects representing the issues related to the character.

        Raises:
            ApiError: If there is an error in the API response data validation.

        """
        resp = self._get_results(["character", _id, "issue_list"])
        adaptor = TypeAdapter(list[BaseIssue])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def publisher(self: Session, _id: int) -> Publisher:
        """Retrieve information about a publisher with the specified ID.

        Args:
            _id: An integer representing the ID of the publisher.

        Returns:
            A Publisher object containing information about the specified publisher.

        """
        resp = self._get(["publisher", _id])
        adaptor = TypeAdapter(Publisher)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def publisher_post(self: Session, data: PublisherPost) -> Publisher:
        """Create a new publisher.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            data: PublisherPost object with the publisher data.

        Returns:
            A Publisher object containing information about the created publisher.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("POST", ["publisher"], data)
        except exceptions.ApiError as error:
            raise exceptions.ApiError(error) from error

        adaptor = TypeAdapter(Publisher)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def publisher_patch(self: Session, id_: int, data: PublisherPost) -> Publisher:
        """Update an existing publisher.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            id_: The ID of the publisher to update.
            data: PublisherPost object with the updated publisher data.

        Returns:
            A Publisher object containing information about the updated publisher.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("PATCH", ["publisher", id_], data)
        except exceptions.ApiError as error:
            raise exceptions.ApiError(error) from error

        adaptor = TypeAdapter(Publisher)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def publishers_list(
        self: Session, params: dict[str, str | int] | None = None
    ) -> list[BaseResource]:
        """Retrieve a list of publishers based on the provided parameters.

        Args:
            params: An optional dictionary of parameters for filtering the list of publishers.

        Returns:
            A list of BaseResource objects representing the publishers that match the criteria.

        Raises:
            ApiError: If there is an error in the API response data validation.

        """
        resp = self._get_results(["publisher"], params)
        adapter = TypeAdapter(list[BaseResource])
        try:
            result = adapter.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def team(self: Session, _id: int) -> Team:
        """Retrieve information about a team with the specified ID.

        Args:
            _id: An integer representing the ID of the team.

        Returns:
            A Team object containing information about the specified team.

        Raises:
            ApiError: If there is an error in the API response data validation.
        """
        resp = self._get(["team", _id])
        adaptor = TypeAdapter(Team)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def team_post(self: Session, data: TeamPost) -> TeamPostResponse:
        """Create a new team.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            data: TeamPost object with the team data.

        Returns:
            A TeamPostResponse object containing information about the created team.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("POST", ["team"], data)
        except exceptions.ApiError as error:
            raise exceptions.ApiError(error) from error

        adaptor = TypeAdapter(TeamPostResponse)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def team_patch(self: Session, id_: int, data: TeamPost) -> TeamPostResponse:
        """Update an existing team.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            id_: The ID of the team to update.
            data: TeamPost object with the updated team data.

        Returns:
            A TeamPostResponse object containing information about the updated team.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("PATCH", ["team", id_], data)
        except exceptions.ApiError as error:
            raise exceptions.ApiError(error) from error

        adaptor = TypeAdapter(TeamPostResponse)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def teams_list(self: Session, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of teams based on the provided parameters.

        Args:
            params: An optional dictionary of parameters for filtering the list of teams.

        Returns:
            A list of BaseResource objects representing the teams that match the criteria.

        Raises:
            ApiError: If there is an error in the API response data validation.

        """
        resp = self._get_results(["team"], params)
        adapter = TypeAdapter(list[BaseResource])
        try:
            result = adapter.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def team_issues_list(self: Session, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues related to a team with the specified ID.

        Args:
            _id: An integer representing the ID of the team.

        Returns:
            A list of BaseIssue objects representing the issues related to the team.

        Raises:
            ApiError: If there is an error in the API response data validation.
        """
        resp = self._get_results(["team", _id, "issue_list"])
        adapter = TypeAdapter(list[BaseIssue])
        try:
            result = adapter.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def arc(self: Session, _id: int) -> Arc:
        """Retrieve information about an arc with the specified ID.

        Args:
            _id: An integer representing the ID of the arc.

        Returns:
            An Arc object containing information about the specified arc.

        Raises:
            ApiError: If there is an error in the API response data validation.
        """
        resp = self._get(["arc", _id])
        adaptor = TypeAdapter(Arc)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def arc_post(self: Session, data: ArcPost) -> Arc:
        """Create a new arc.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            data: ArcPost object with the arc data.

        Returns:
            An Arc object containing information about the created arc.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("POST", ["arc"], data)
        except exceptions.ApiError as error:
            raise exceptions.ApiError(error) from error

        adaptor = TypeAdapter(Arc)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def arc_patch(self: Session, id_: int, data: ArcPost) -> Arc:
        """Update an existing arc.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            id_: The ID of the arc to update.
            data: ArcPost object with the updated arc data.

        Returns:
            An Arc object containing information about the updated arc.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("PATCH", ["arc", id_], data)
        except exceptions.ApiError as error:
            raise exceptions.ApiError(error) from error

        adaptor = TypeAdapter(Arc)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def arcs_list(self: Session, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of arcs based on the provided parameters.

        Args:
            params: An optional dictionary of parameters for filtering the list of arcs.

        Returns:
            A list of BaseResource objects representing the arcs that match the criteria.

        Raises:
            ApiError: If there is an error in the API response data validation.
        """
        resp = self._get_results(["arc"], params)
        adapter = TypeAdapter(list[BaseResource])
        try:
            result = adapter.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def arc_issues_list(self: Session, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues related to an arc with the specified ID.

        Args:
            _id: An integer representing the ID of the arc.

        Returns:
            A list of BaseIssue objects representing the issues related to the arc.

        Raises:
            ApiError: If there is an error in the API response data validation.
        """
        resp = self._get_results(["arc", _id, "issue_list"])
        adaptor = TypeAdapter(list[BaseIssue])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def series(self: Session, _id: int) -> Series:
        """Retrieve information about a series with the specified ID.

        Args:
            _id: An integer representing the ID of the series.

        Returns:
            A Series object containing information about the specified series.

        Raises:
            ApiError: If there is an error in the API response data validation.
        """
        resp = self._get(["series", _id])
        adaptor = TypeAdapter(Series)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def series_post(self: Session, data: SeriesPost) -> SeriesPostResponse:
        """Create a new series.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            data: SeriesPost object with the series data.

        Returns:
            A SeriesPostResponse object containing information about the created series.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("POST", ["series"], data)
        except ApiError as err:
            raise exceptions.ApiError(err) from err

        adaptor = TypeAdapter(SeriesPostResponse)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def series_patch(self: Session, id_: int, data: SeriesPost) -> SeriesPostResponse:
        """Update an existing series.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            id_: The ID of the series to update.
            data: SeriesPost object with the updated series data.

        Returns:
            A SeriesPostResponse object containing information about the updated series.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("PATCH", ["series", id_], data)
        except exceptions.ApiError as err:
            raise exceptions.ApiError(err) from err

        adaptor = TypeAdapter(SeriesPostResponse)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def series_list(self: Session, params: dict[str, str | int] | None = None) -> list[BaseSeries]:
        """Retrieve a list of series based on the provided parameters.

        Args:
            params: An optional dictionary of parameters for filtering the list of series.

        Returns:
            A list of BaseSeries objects representing the series that match the criteria.

        Raises:
            ApiError: If there is an error in the API response data validation.
        """
        resp = self._get_results(["series"], params)
        adaptor = TypeAdapter(list[BaseSeries])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def series_type_list(
        self: Session, params: dict[str, str | int] | None = None
    ) -> list[GenericItem]:
        """Retrieve a list of series types based on the provided parameters.

        Args:
            params: An optional dictionary of parameters for filtering the list of series types.

        Returns:
            A list of GenericItem objects representing the series types that match the criteria.

        Raises:
            ApiError: If there is an error in the API response data validation.
        """
        resp = self._get_results(["series_type"], params)
        adaptor = TypeAdapter(list[GenericItem])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def issue(self: Session, _id: int) -> Issue:
        """Retrieve information about an issue with the specified ID.

        Args:
            _id: An integer representing the ID of the issue.

        Returns:
            An Issue object containing information about the specified issue.

        Raises:
            ApiError: If there is an error in the API response data validation.
        """
        resp = self._get(["issue", _id])
        adaptor = TypeAdapter(Issue)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def issue_post(self: Session, data: IssuePost) -> IssuePostResponse:
        """Create a new issue.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            data: IssuePost object with the issue data.

        Returns:
            An IssuePostResponse object containing information about the created issue.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("POST", ["issue"], data)
        except exceptions.ApiError as err:
            raise exceptions.ApiError(err) from err

        adaptor = TypeAdapter(IssuePostResponse)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def issue_patch(self: Session, id_: int, data: IssuePost) -> IssuePostResponse:
        """Update an existing issue.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            id_: The ID of the issue to update.
            data: IssuePost object with the updated issue data.

        Returns:
            An IssuePostResponse object containing information about the updated issue.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("PATCH", ["issue", id_], data)
        except exceptions.ApiError as err:
            raise exceptions.ApiError(err) from err

        adaptor = TypeAdapter(IssuePostResponse)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def issues_list(self: Session, params: dict[str, str | int] | None = None) -> list[BaseIssue]:
        """Retrieve a list of issues based on the provided parameters.

        Args:
            params: An optional dictionary of parameters for filtering the list of issues.

        Returns:
            A list of BaseIssue objects representing the issues that match the criteria.

        Raises:
            ApiError: If there is an error in the API response data validation.
        """
        resp = self._get_results(["issue"], params)
        adaptor = TypeAdapter(list[BaseIssue])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def credits_post(self: Session, data: list[CreditPost]) -> CreditPostResponse:
        """Create new credits.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            data: A list of CreditPost objects with the credit data.

        Returns:
            A list of CreditPostResponse objects.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("POST", ["credit"], data)
        except exceptions.ApiError as err:
            raise exceptions.ApiError(err) from err

        adaptor = TypeAdapter(list[CreditPostResponse])
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def variant_post(self: Session, data: VariantPost) -> VariantPostResponse:
        """Create a new variant cover.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            data: VariantPost object with the variant data.

        Returns:
            A VariantPostResponse object containing information about the created variant.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("POST", ["variant"], data)
        except exceptions.ApiError as err:
            raise exceptions.ApiError(err) from err

        adaptor = TypeAdapter(VariantPostResponse)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def role_list(self: Session, params: dict[str, str | int] | None = None) -> list[GenericItem]:
        """Retrieve a list of roles based on the provided parameters.

        Args:
            params: An optional dictionary of parameters for filtering the list of roles.

        Returns:
            A list of GenericItem objects representing the roles that match the criteria.

        Raises:
            ApiError: If there is an error in the API response data validation.
        """
        resp = self._get_results(["role"], params)
        adaptor = TypeAdapter(list[GenericItem])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def universe(self: Session, _id: int) -> Universe:
        """Retrieve information about a universe with the specified ID.

        Args:
            _id: An integer representing the ID of the universe.

        Returns:
            A Universe object containing information about the specified universe.

        Raises:
            ApiError: If there is an error in the API response data validation.
        """
        resp = self._get(["universe", _id])
        adaptor = TypeAdapter(Universe)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def universe_post(self: Session, data: UniversePost) -> UniversePostResponse:
        """Create a new universe.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            data: UniversePost object with the universe data.

        Returns:
            A UniversePostResponse object containing information about the created universe.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("POST", ["universe"], data)
        except exceptions.ApiError as err:
            raise exceptions.ApiError(err) from err

        adaptor = TypeAdapter(UniversePostResponse)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def universe_patch(self: Session, id_: int, data: UniversePost) -> UniversePostResponse:
        """Update an existing universe.

        Note: This function only works for users with Admin permissions at Metron.

        Args:
            id_: The ID of the universe to update.
            data: UniversePost object with the updated universe data.

        Returns:
            A UniversePostResponse object containing information about the updated universe.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        try:
            resp = self._send("PATCH", ["universe", id_], data)
        except exceptions.ApiError as err:
            raise exceptions.ApiError(err) from err

        adaptor = TypeAdapter(UniversePostResponse)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def universes_list(
        self: Session, params: dict[str, str | int] | None = None
    ) -> list[BaseResource]:
        """Retrieve a list of universes based on the provided parameters.

        Args:
            params: An optional dictionary of parameters for filtering the list of universes.

        Returns:
            A list of BaseResource objects representing the universes that match the criteria.

        Raises:
            ApiError: If there is an error in the API response data validation.
        """
        resp = self._get_results(["universe"], params)
        adapter = TypeAdapter(list[BaseResource])
        try:
            result = adapter.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def imprint(self: Session, _id: int) -> Imprint:
        """Retrieves an imprint by ID.

        Args:
            _id: The ID of the imprint to retrieve.

        Returns:
            Imprint: The retrieved imprint object.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        resp = self._get(["imprint", _id])
        adaptor = TypeAdapter(Imprint)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def imprints_list(
        self: Session, params: dict[str, str | int] | None = None
    ) -> list[BaseResource]:
        """Retrieves a list of imprints based on the provided parameters.

        Args:
            params: A dictionary containing parameters for filtering imprints (optional).

        Returns:
            list[BaseResource]: A list of BaseResource objects representing the retrieved imprints.

        Raises:
            ApiError: If there is an error during the API call or validation.
        """
        resp = self._get_results(["imprint"], params)
        adapter = TypeAdapter(list[BaseResource])
        try:
            result = adapter.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def _get_results(
        self: Session,
        endpoint: list[str | int],
        params: dict[str, str | int] | None = None,
    ) -> dict[str, Any]:
        """Retrieve results from the specified API endpoint with optional parameters.

        Args:
            endpoint: A list of strings or integers representing the endpoint path.
            params: A dictionary of parameters to be included in the request URL.

        Returns:
            A dictionary containing the response data from the API.
        """
        if params is None:
            params = {}

        result = self._get(endpoint, params=params)
        if result["next"]:
            result = self._retrieve_all_results(result)
        return result

    def _retrieve_all_results(self: Session, data: dict[str, Any]) -> dict[str, Any]:
        """Retrieve all results from paginated data by following the 'next' links.

        Args:
            data: A dictionary containing the initial response data with pagination information.

        Returns:
            A dictionary containing all results retrieved by following the pagination links.
        """
        has_next_page = True
        next_page = data["next"]

        while has_next_page:
            if cached_response := self._get_results_from_cache(next_page):
                data["results"].extend(cached_response["results"])
                if cached_response["next"]:
                    next_page = cached_response["next"]
                else:
                    has_next_page = False
                continue

            response = self._request_data("GET", next_page)
            data["results"].extend(response["results"])

            self._save_results_to_cache(next_page, response)

            if response["next"]:
                next_page = response["next"]
            else:
                has_next_page = False

        return data

    @decorator(rate_mapping)
    def _request_data(
        self: Session,
        method: str,
        url: str,
        params: dict[str, str | int] | None = None,
        data: T | None = None,
    ) -> Any:
        LOGGER.debug("Request Method: %s | URL: %s", method, url)
        LOGGER.debug("Original Header: %s", self.header)

        if params is None:
            params = {}

        files = None
        if isinstance(data, list):
            lst = []
            lst.extend(item.model_dump() for item in data)
            data_dict = json.dumps(lst)
            header = self.header.copy()
            header["Content-Type"] = "application/json;charset=utf-8"
        else:
            data_dict = data.model_dump() if data else None
            if data_dict is not None and "image" in data_dict:  # NOQA: SIM102
                if img := data_dict.pop("image"):
                    img_path = Path(img)
                    files = {"image": (img_path.name, img_path.read_bytes())}
                    LOGGER.debug("Image File: %s", img)
            header = self.header

        LOGGER.debug("Header: %s", header)
        LOGGER.debug("Data: %s", data_dict)
        LOGGER.debug("Params: %s", params)

        try:
            response = requests.request(
                method,
                url,
                params=params,
                timeout=20,
                auth=(self.username, self.passwd),
                headers=header,
                data=data_dict,
                files=files,
            )
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
        ) as e:
            raise exceptions.ApiError(f"Connection error: {e!r}") from e

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise exceptions.ApiError(f"HTTP error: {e!r}") from e

        resp = response.json()
        if "detail" in resp:
            raise exceptions.ApiError(resp["detail"])
        return resp

    def _get_results_from_cache(self: Session, key: str) -> Any | None:
        """Retrieve cached response data using the specified key.

        Args:
            key: A string representing the key to retrieve cached data.

        Returns:
            The cached response data if available, or None if not found.

        Raises:
            CacheError: If there is an issue with the cache object.
        """
        cached_response = None

        if self.cache:
            try:
                cached_response = self.cache.get(key)
            except AttributeError as e:
                raise exceptions.CacheError(
                    f"Cache object passed in is missing attribute: {e!r}"
                ) from e

        return cached_response

    def _save_results_to_cache(self: Session, key: str, data: str) -> None:
        """Store the provided data in the cache using the specified key.

        Args:
            key: A string representing the key to store the data in the cache.
            data: The data to be stored in the cache.

        Returns:
            None

        Raises:
            CacheError: If there is an issue with the cache object.
        """
        if self.cache:
            try:
                self.cache.store(key, data)
            except AttributeError as e:
                raise exceptions.CacheError(
                    f"Cache object passed in is missing attribute: {e!r}"
                ) from e

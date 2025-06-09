# ruff: noqa: TRY003
"""Session module.

This module provides the following classes:

- Session
"""

__all__ = ["Session"]

import json
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Any, ClassVar, TypeVar
from urllib.parse import urlencode

import requests
from pydantic import TypeAdapter, ValidationError
from pyrate_limiter import Duration, Limiter, Rate, SQLiteBucket

from mokkari import __version__, exceptions, sqlite_cache
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

# Constants
METRON_MINUTE_RATE_LIMIT = 30
METRON_DAY_RATE_LIMIT = 10_000
METRON_URL = "https://metron.cloud/api/{}/"
LOCAL_URL = "http://127.0.0.1:8000/api/{}/"
REQUEST_TIMEOUT = 20


def rate_mapping(*args: Any, **kwargs: Any) -> tuple[str, int]:  # noqa: ARG001
    """Map rate limiting parameters."""
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
        self,
        username: str,
        passwd: str,
        cache: sqlite_cache.SqliteCache | None = None,
        user_agent: str | None = None,
        dev_mode: bool = False,
    ) -> None:
        """Initialize a Session object with the provided username, password, cache, and user agent."""
        import platform

        self.username = username
        self.passwd = passwd
        self.header = {
            "User-Agent": f"{f'{user_agent} ' if user_agent is not None else ''}"
            f"Mokkari/{__version__} ({platform.system()}; {platform.release()})"
        }
        self.api_url = LOCAL_URL if dev_mode else METRON_URL
        self.cache = cache

    def _get(
        self,
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

    def _send(self, method: str, endpoint: list[str | int], data: T) -> Any:
        """Send a request to the specified endpoint with the given data.

        Args:
            method: The HTTP method for the request.
            endpoint: A list of strings or integers representing the endpoint path.
            data: The data to be sent with the request.

        Returns:
            The response data from the API.

        Raises:
            ApiError: If there is an error during the API call.
        """
        url = self.api_url.format("/".join(str(e) for e in endpoint))
        return self._request_data(method=method, url=url, data=data)

    @staticmethod
    def _validate_response(resp: dict[str, Any], adapter_class: type) -> Any:
        """Validate API response using the provided adapter class.

        Args:
            resp: The response dictionary to validate.
            adapter_class: The Pydantic type adapter class to use for validation.

        Returns:
            The validated response object.

        Raises:
            ApiError: If validation fails.
        """
        adapter = TypeAdapter(adapter_class)
        try:
            return adapter.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error

    @staticmethod
    def _validate_list_response(resp: dict[str, Any], item_class: type) -> list[Any]:
        """Validate API response containing a list of items.

        Args:
            resp: The response dictionary to validate.
            item_class: The class type for list items.

        Returns:
            The validated list of objects.

        Raises:
            ApiError: If validation fails.
        """
        adapter = TypeAdapter(list[item_class])
        try:
            return adapter.validate_python(resp["results"])
        except ValidationError as error:
            raise exceptions.ApiError(error) from error

    def _handle_post_request(self, endpoint: list[str], data: Any, response_class: type) -> Any:
        """Handle POST request with consistent error handling and validation.

        Args:
            endpoint: The API endpoint path.
            data: The data to send.
            response_class: The expected response class for validation.

        Returns:
            The validated response object.

        Raises:
            ApiError: If the request or validation fails.
        """
        try:
            resp = self._send("POST", endpoint, data)
        except exceptions.ApiError as error:
            raise exceptions.ApiError(error) from error

        return self._validate_response(resp, response_class)

    def _handle_patch_request(
        self, endpoint: list[str | int], data: Any, response_class: type
    ) -> Any:
        """Handle PATCH request with consistent error handling and validation.

        Args:
            endpoint: The API endpoint path.
            data: The data to send.
            response_class: The expected response class for validation.

        Returns:
            The validated response object.

        Raises:
            ApiError: If the request or validation fails.
        """
        try:
            resp = self._send("PATCH", endpoint, data)
        except exceptions.ApiError as error:
            raise exceptions.ApiError(error) from error

        return self._validate_response(resp, response_class)

    # Creator methods
    def creator(self, _id: int) -> Creator:
        """Retrieve information about a creator with the specified ID."""
        resp = self._get(["creator", _id])
        return self._validate_response(resp, Creator)

    def creator_post(self, data: CreatorPost) -> Creator:
        """Create a new creator.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_post_request(["creator"], data, Creator)

    def creator_patch(self, _id: int, data: CreatorPost) -> Creator:
        """Update an existing creator.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_patch_request(["creator", _id], data, Creator)

    def creators_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of creators based on the provided parameters."""
        resp = self._get_results(["creator"], params)
        return self._validate_list_response(resp, BaseResource)

    # Character methods
    def character(self, _id: int) -> Character:
        """Retrieve information about a character with the specified ID."""
        resp = self._get(["character", _id])
        return self._validate_response(resp, Character)

    def character_post(self, data: CharacterPost) -> CharacterPostResponse:
        """Create a new character.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_post_request(["character"], data, CharacterPostResponse)

    def character_patch(self, _id: int, data: CharacterPost) -> CharacterPostResponse:
        """Update an existing character.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_patch_request(["character", _id], data, CharacterPostResponse)

    def characters_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of characters based on the provided parameters."""
        resp = self._get_results(["character"], params)
        return self._validate_list_response(resp, BaseResource)

    def character_issues_list(self, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues related to a character with the specified ID."""
        resp = self._get_results(["character", _id, "issue_list"])
        return self._validate_list_response(resp, BaseIssue)

    # Publisher methods
    def publisher(self, _id: int) -> Publisher:
        """Retrieve information about a publisher with the specified ID."""
        resp = self._get(["publisher", _id])
        return self._validate_response(resp, Publisher)

    def publisher_post(self, data: PublisherPost) -> Publisher:
        """Create a new publisher.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_post_request(["publisher"], data, Publisher)

    def publisher_patch(self, _id: int, data: PublisherPost) -> Publisher:
        """Update an existing publisher.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_patch_request(["publisher", _id], data, Publisher)

    def publishers_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of publishers based on the provided parameters."""
        resp = self._get_results(["publisher"], params)
        return self._validate_list_response(resp, BaseResource)

    # Team methods
    def team(self, _id: int) -> Team:
        """Retrieve information about a team with the specified ID."""
        resp = self._get(["team", _id])
        return self._validate_response(resp, Team)

    def team_post(self, data: TeamPost) -> TeamPostResponse:
        """Create a new team.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_post_request(["team"], data, TeamPostResponse)

    def team_patch(self, _id: int, data: TeamPost) -> TeamPostResponse:
        """Update an existing team.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_patch_request(["team", _id], data, TeamPostResponse)

    def teams_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of teams based on the provided parameters."""
        resp = self._get_results(["team"], params)
        return self._validate_list_response(resp, BaseResource)

    def team_issues_list(self, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues related to a team with the specified ID."""
        resp = self._get_results(["team", _id, "issue_list"])
        return self._validate_list_response(resp, BaseIssue)

    # Arc methods
    def arc(self, _id: int) -> Arc:
        """Retrieve information about an arc with the specified ID."""
        resp = self._get(["arc", _id])
        return self._validate_response(resp, Arc)

    def arc_post(self, data: ArcPost) -> Arc:
        """Create a new arc.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_post_request(["arc"], data, Arc)

    def arc_patch(self, _id: int, data: ArcPost) -> Arc:
        """Update an existing arc.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_patch_request(["arc", _id], data, Arc)

    def arcs_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of arcs based on the provided parameters."""
        resp = self._get_results(["arc"], params)
        return self._validate_list_response(resp, BaseResource)

    def arc_issues_list(self, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues related to an arc with the specified ID."""
        resp = self._get_results(["arc", _id, "issue_list"])
        return self._validate_list_response(resp, BaseIssue)

    # Series methods
    def series(self, _id: int) -> Series:
        """Retrieve information about a series with the specified ID."""
        resp = self._get(["series", _id])
        return self._validate_response(resp, Series)

    def series_post(self, data: SeriesPost) -> SeriesPostResponse:
        """Create a new series.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_post_request(["series"], data, SeriesPostResponse)

    def series_patch(self, _id: int, data: SeriesPost) -> SeriesPostResponse:
        """Update an existing series.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_patch_request(["series", _id], data, SeriesPostResponse)

    def series_list(self, params: dict[str, str | int] | None = None) -> list[BaseSeries]:
        """Retrieve a list of series based on the provided parameters."""
        resp = self._get_results(["series"], params)
        return self._validate_list_response(resp, BaseSeries)

    def series_type_list(self, params: dict[str, str | int] | None = None) -> list[GenericItem]:
        """Retrieve a list of series types based on the provided parameters."""
        resp = self._get_results(["series_type"], params)
        return self._validate_list_response(resp, GenericItem)

    # Issue methods
    def issue(self, _id: int) -> Issue:
        """Retrieve information about an issue with the specified ID."""
        resp = self._get(["issue", _id])
        return self._validate_response(resp, Issue)

    def issue_post(self, data: IssuePost) -> IssuePostResponse:
        """Create a new issue.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_post_request(["issue"], data, IssuePostResponse)

    def issue_patch(self, _id: int, data: IssuePost) -> IssuePostResponse:
        """Update an existing issue.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_patch_request(["issue", _id], data, IssuePostResponse)

    def issues_list(self, params: dict[str, str | int] | None = None) -> list[BaseIssue]:
        """Retrieve a list of issues based on the provided parameters."""
        resp = self._get_results(["issue"], params)
        return self._validate_list_response(resp, BaseIssue)

    def credits_post(self, data: list[CreditPost]) -> list[CreditPostResponse]:
        """Create new credits.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_post_request(["credit"], data, list[CreditPostResponse])

    def variant_post(self, data: VariantPost) -> VariantPostResponse:
        """Create a new variant cover.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_post_request(["variant"], data, VariantPostResponse)

    def role_list(self, params: dict[str, str | int] | None = None) -> list[GenericItem]:
        """Retrieve a list of roles based on the provided parameters."""
        resp = self._get_results(["role"], params)
        return self._validate_list_response(resp, GenericItem)

    # Universe methods
    def universe(self, _id: int) -> Universe:
        """Retrieve information about a universe with the specified ID."""
        resp = self._get(["universe", _id])
        return self._validate_response(resp, Universe)

    def universe_post(self, data: UniversePost) -> UniversePostResponse:
        """Create a new universe.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_post_request(["universe"], data, UniversePostResponse)

    def universe_patch(self, _id: int, data: UniversePost) -> UniversePostResponse:
        """Update an existing universe.

        Note: This function only works for users with Admin permissions at Metron.
        """
        return self._handle_patch_request(["universe", _id], data, UniversePostResponse)

    def universes_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of universes based on the provided parameters."""
        resp = self._get_results(["universe"], params)
        return self._validate_list_response(resp, BaseResource)

    # Imprint methods
    def imprint(self, _id: int) -> Imprint:
        """Retrieve an imprint by ID."""
        resp = self._get(["imprint", _id])
        return self._validate_response(resp, Imprint)

    def imprints_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of imprints based on the provided parameters."""
        resp = self._get_results(["imprint"], params)
        return self._validate_list_response(resp, BaseResource)

    def _get_results(
        self,
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

    def _retrieve_all_results(self, data: dict[str, Any]) -> dict[str, Any]:
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
        self,
        method: str,
        url: str,
        params: dict[str, str | int] | None = None,
        data: T | None = None,
    ) -> Any:
        """Make HTTP request with rate limiting and error handling."""
        LOGGER.debug("Request Method: %s | URL: %s", method, url)
        LOGGER.debug("Original Header: %s", self.header)

        if params is None:
            params = {}

        files = None
        data_dict = None
        header = self.header.copy()

        if isinstance(data, list):
            # Handle list data (e.g., credits)
            lst = [item.model_dump() for item in data]
            data_dict = json.dumps(lst)
            header["Content-Type"] = "application/json;charset=utf-8"
        elif data is not None:
            # Handle single object data
            data_dict = data.model_dump()

            # Handle image uploads
            if data_dict and "image" in data_dict and (img := data_dict.pop("image")):
                img_path = Path(img)
                if img_path.exists():
                    files = {"image": (img_path.name, img_path.read_bytes())}
                    LOGGER.debug("Image File: %s", img)
                else:
                    LOGGER.warning("Image file not found: %s", img)

        LOGGER.debug("Header: %s", header)
        LOGGER.debug("Data: %s", data_dict)
        LOGGER.debug("Params: %s", params)

        try:
            response = requests.request(
                method,
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
                auth=(self.username, self.passwd),
                headers=header,
                data=data_dict,
                files=files,
            )
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
        ) as e:
            msg = f"Connection error: {e!r}"
            raise exceptions.ApiError(msg) from e

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            msg = f"HTTP error: {e!r}"
            raise exceptions.ApiError(msg) from e

        try:
            resp = response.json()
        except ValueError as e:
            msg = f"Invalid JSON response: {e!r}"
            raise exceptions.ApiError(msg) from e

        if "detail" in resp:
            raise exceptions.ApiError(resp["detail"])

        return resp

    def _get_results_from_cache(self, key: str) -> Any | None:
        """Retrieve cached response data using the specified key.

        Args:
            key: A string representing the key to retrieve cached data.

        Returns:
            The cached response data if available, or None if not found.

        Raises:
            CacheError: If there is an issue with the cache object.
        """
        if not self.cache:
            return None

        try:
            return self.cache.get(key)
        except AttributeError as e:
            msg = f"Cache object passed in is missing attribute: {e!r}"
            raise exceptions.CacheError(msg) from e

    def _save_results_to_cache(self, key: str, data: Any) -> None:
        """Store the provided data in the cache using the specified key.

        Args:
            key: A string representing the key to store the data in the cache.
            data: The data to be stored in the cache.

        Raises:
            CacheError: If there is an issue with the cache object.
        """
        if not self.cache:
            return

        try:
            self.cache.store(key, data)
        except AttributeError as e:
            msg = f"Cache object passed in is missing attribute: {e!r}"
            raise exceptions.CacheError(msg) from e

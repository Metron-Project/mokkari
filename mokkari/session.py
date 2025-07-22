"""Session module.

This module provides the following classes:

- Session: Main API client for interacting with the Metron Comics Database
"""

__all__ = ["Session"]

import json
import logging
import platform
from collections import OrderedDict
from pathlib import Path
from typing import Any, ClassVar, Final, TypeVar
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
METRON_MINUTE_RATE_LIMIT: Final[int] = 30
METRON_DAY_RATE_LIMIT: Final[int] = 10_000
REQUEST_TIMEOUT: Final[int] = 20
SECONDS_PER_HOUR: Final[int] = 3_600
SECONDS_PER_MINUTE: Final[int] = 60
METRON_URL = "https://metron.cloud/api/{}/"
LOCAL_URL = "http://127.0.0.1:8000/api/{}/"


def rate_mapping(*args: Any, **kwargs: Any) -> tuple[str, int]:  # noqa: ARG001
    """Map rate limiting parameters for the rate limiter.

    This function provides a consistent rate limiting key for all API requests.

    Args:
        *args: Variable length argument list (unused).
        **kwargs: Arbitrary keyword arguments (unused).

    Returns:
        tuple[str, int]: A tuple containing the rate limiting key and count.
    """
    return "metron", 1


def format_time(seconds: str | float) -> str:
    """Format seconds into a verbose human-readable time string.

    Args:
        seconds: Number of seconds to format. Can be a string or float.

    Returns:
        str: Formatted time string (e.g., "2 hours, 30 minutes, 45 seconds").

    Examples:
        >>> format_time(3661)
        "1 hour, 1 minute, 1 second"
        >>> format_time(90)
        "1 minute, 30 seconds"
        >>> format_time(0)
        "0 seconds"
    """
    total_seconds = int(seconds)

    if total_seconds < 0:
        return "0 seconds"

    hours = total_seconds // SECONDS_PER_HOUR
    minutes = (total_seconds % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE
    remaining_seconds = total_seconds % SECONDS_PER_MINUTE

    parts = []

    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")

    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

    if remaining_seconds > 0 or not parts:
        parts.append(f"{remaining_seconds} second{'s' if remaining_seconds != 1 else ''}")

    return ", ".join(parts)


class Session:
    """A comprehensive API client for interacting with the Metron Comics Database.

    The Session class provides a complete interface for accessing comic book data including
    creators, characters, publishers, series, issues, teams, arcs, and more. It handles
    authentication, rate limiting, caching, and response validation automatically.

    The class implements automatic rate limiting to respect API quotas:

    - 30 requests per minute
    - 10,000 requests per day

    Features:

    - Automatic authentication with username/password
    - Built-in rate limiting and retry logic
    - Optional SQLite caching for improved performance
    - Comprehensive error handling and validation
    - Support for both read and write operations (write operations require admin permissions)
    - Automatic pagination handling for large result sets
    - Image upload support for certain endpoints
    - Development mode for testing against a local instances of Metron.

    Args:
        username: Username for Metron API authentication.
        passwd: Password for Metron API authentication.
        cache: Optional SqliteCache instance for caching responses to improve performance.
        user_agent: Optional custom user agent string to append to the default user agent.
        dev_mode: If True, connects to local development instance at 127.0.0.1:8000 instead of production.

    Attributes:
        username (str): The username used for API authentication.
        passwd (str): The password used for API authentication.
        header (dict): HTTP headers sent with each request, including User-Agent.
        api_url (str): The base URL for API requests (production or development).
        cache (SqliteCache | None): The cache instance if provided.

    Examples:
        Basic usage:
        >>> session = Session("username", "password")
        >>> issue = session.issue(1)
        >>> print(issue)

        With caching:
        >>> from mokkari.sqlite_cache import SqliteCache
        >>> cache = SqliteCache("cache.db")
        >>> session = Session("username", "password", cache=cache)

        Development mode:
        >>> session = Session("username", "password", dev_mode=True)

    Raises:
        ApiError: For general API errors, authentication failures, or network issues.
        RateLimitError: When API rate limits are exceeded.
        CacheError: For cache-related errors.
        ValidationError: For invalid response data that doesn't match expected schemas.
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
        """Initialize a Session object with authentication and configuration.

        Sets up the session with proper authentication headers, API endpoint URL,
        and optional caching. The user agent is automatically constructed to include
        the library version and system information.

        Args:
            username: Username for Metron API authentication.
            passwd: Password for Metron API authentication.
            cache: Optional SqliteCache instance for response caching.
            user_agent: Optional custom user agent string to prepend to the default.
            dev_mode: If True, use local development server instead of production.
        """
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
        """Send a GET request to the specified endpoint with optional parameters.

        This internal method handles GET requests with caching support. It first checks
        the cache for existing data, and if not found, makes the API request and caches
        the result for future use.

        Args:
            endpoint: List of path segments to build the API endpoint URL.
            params: Optional query parameters to include in the request.

        Returns:
            dict[str, Any]: The response data from the API.

        Raises:
            ApiError: If the API returns an error response or if there are network issues.
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
        """Send a request with data to the specified endpoint.

        This internal method handles POST and PATCH requests with data payloads.
        It supports both single objects and lists of objects, as well as file uploads.

        Args:
            method: HTTP method to use ("POST" or "PATCH").
            endpoint: List of path segments to build the API endpoint URL.
            data: The data object to send in the request body.

        Returns:
            Any: The response data from the API.

        Raises:
            ApiError: If there is an error during the API call.
        """
        url = self.api_url.format("/".join(str(e) for e in endpoint))
        return self._request_data(method=method, url=url, data=data)

    @staticmethod
    def _validate_response(resp: dict[str, Any], adapter_class: type) -> Any:
        """Validate API response using the provided Pydantic adapter class.

        This method ensures that the API response conforms to the expected schema
        by validating it against the appropriate Pydantic model.

        Args:
            resp: The response dictionary from the API to validate.
            adapter_class: The Pydantic type adapter class for validation.

        Returns:
            Any: The validated response object.

        Raises:
            ApiError: If validation fails due to schema mismatch.
        """
        adapter = TypeAdapter(adapter_class)
        try:
            return adapter.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error

    @staticmethod
    def _validate_list_response(resp: dict[str, Any], item_class: type) -> list[Any]:
        """Validate API response containing a list of items.

        This method validates paginated responses that contain a 'results' field
        with a list of items that should conform to the specified schema.

        Args:
            resp: The response dictionary containing a 'results' field with list data.
            item_class: The class type that each item in the list should conform to.

        Returns:
            list[Any]: The validated list of objects.

        Raises:
            ApiError: If validation fails for any item in the list.
        """
        adapter = TypeAdapter(list[item_class])
        try:
            return adapter.validate_python(resp["results"])
        except ValidationError as error:
            raise exceptions.ApiError(error) from error

    def _handle_post_request(self, endpoint: list[str], data: Any, response_class: type) -> Any:
        """Handle POST request with consistent error handling and validation.

        This internal method provides a standardized way to handle POST requests
        with proper error handling and response validation.

        Args:
            endpoint: The API endpoint path segments.
            data: The data to send in the POST request.
            response_class: The expected response class for validation.

        Returns:
            Any: The validated response object.

        Raises:
            ApiError: If the request fails or validation fails.
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

        This internal method provides a standardized way to handle PATCH requests
        with proper error handling and response validation.

        Args:
            endpoint: The API endpoint path segments.
            data: The data to send in the PATCH request.
            response_class: The expected response class for validation.

        Returns:
            Any: The validated response object.

        Raises:
            ApiError: If the request fails or validation fails.
        """
        try:
            resp = self._send("PATCH", endpoint, data)
        except exceptions.ApiError as error:
            raise exceptions.ApiError(error) from error

        return self._validate_response(resp, response_class)

    # Creator methods
    def creator(self, _id: int) -> Creator:
        """Retrieve detailed information about a creator by ID.

        Args:
            _id: The unique identifier for the creator.

        Returns:
            Creator: A Creator object containing detailed information about the creator.

        Raises:
            ApiError: If the creator is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("username", "password")
            >>> creator = session.creator(1)
            >>> print(creator.name)
            >>> print(creator.birth_date)
        """
        resp = self._get(["creator", _id])
        return self._validate_response(resp, Creator)

    def creator_post(self, data: CreatorPost) -> Creator:
        """Create a new creator in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: CreatorPost object containing the creator information to create.

        Returns:
            Creator: The newly created Creator object.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("username", "password")
            >>> creator_data = CreatorPost(name="Jane Doe", birth_date="1980-01-01")
            >>> new_creator = session.creator_post(creator_data)
        """
        return self._handle_post_request(["creator"], data, Creator)

    def creator_patch(self, _id: int, data: CreatorPost) -> Creator:
        """Update an existing creator in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the creator to update.
            data: CreatorPost object containing the updated creator information.

        Returns:
            Creator: The updated Creator object.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("username", "password")
            >>> creator_data = CreatorPost(name="Jane Doe", birth_date="1980-01-01")
            >>> updated_creator = session.creator_patch(1, creator_data)
        """
        return self._handle_patch_request(["creator", _id], data, Creator)

    def creators_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of creators with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing creators.

        Examples:
            >>> session = Session("username", "password")
            >>> creators = session.creators_list({"name": "Stan Lee"})
            >>> all_creators = session.creators_list()
        """
        resp = self._get_results(["creator"], params)
        return self._validate_list_response(resp, BaseResource)

    # Character methods
    def character(self, _id: int) -> Character:
        """Retrieve detailed information about a character by ID.

        Args:
            _id: The unique identifier for the character.

        Returns:
            Character: A Character object containing detailed character information.

        Raises:
            ApiError: If the character is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("username", "password")
            >>> character = session.character(1)
            >>> print(character.name)
            >>> print(character.alias)
        """
        resp = self._get(["character", _id])
        return self._validate_response(resp, Character)

    def character_post(self, data: CharacterPost) -> CharacterPostResponse:
        """Create a new character in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: CharacterPost object containing the character information to create.

        Returns:
            CharacterPostResponse: The newly created character response.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
        """
        return self._handle_post_request(["character"], data, CharacterPostResponse)

    def character_patch(self, _id: int, data: CharacterPost) -> CharacterPostResponse:
        """Update an existing character in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the character to update.
            data: CharacterPost object containing the updated character information.

        Returns:
            CharacterPostResponse: The updated character response.

        Raises:
            ApiError: If update fails or if user lacks permissions.
        """
        return self._handle_patch_request(["character", _id], data, CharacterPostResponse)

    def characters_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of characters with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing characters.
        """
        resp = self._get_results(["character"], params)
        return self._validate_list_response(resp, BaseResource)

    def character_issues_list(self, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues featuring a specific character.

        Args:
            _id: The unique identifier for the character.

        Returns:
            list[BaseIssue]: A list of BaseIssue objects representing issues featuring the character.

        Examples:
            >>> session = Session("username", "password")
            >>> issues = session.character_issues_list(1)
            >>> print(f"Character appears in {len(issues)} issues")
        """
        resp = self._get_results(["character", _id, "issue_list"])
        return self._validate_list_response(resp, BaseIssue)

    # Publisher methods
    def publisher(self, _id: int) -> Publisher:
        """Retrieve detailed information about a publisher by ID.

        Args:
            _id: The unique identifier for the publisher.

        Returns:
            Publisher: A Publisher object containing detailed publisher information.

        Raises:
            ApiError: If the publisher is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        resp = self._get(["publisher", _id])
        return self._validate_response(resp, Publisher)

    def publisher_post(self, data: PublisherPost) -> Publisher:
        """Create a new publisher in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: PublisherPost object containing the publisher information to create.

        Returns:
            Publisher: The newly created Publisher object.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
        """
        return self._handle_post_request(["publisher"], data, Publisher)

    def publisher_patch(self, _id: int, data: PublisherPost) -> Publisher:
        """Update an existing publisher in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the publisher to update.
            data: PublisherPost object containing the updated publisher information.

        Returns:
            Publisher: The updated Publisher object.

        Raises:
            ApiError: If update fails or if user lacks permissions.
        """
        return self._handle_patch_request(["publisher", _id], data, Publisher)

    def publishers_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of publishers with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing publishers.
        """
        resp = self._get_results(["publisher"], params)
        return self._validate_list_response(resp, BaseResource)

    # Team methods
    def team(self, _id: int) -> Team:
        """Retrieve detailed information about a team by ID.

        Args:
            _id: The unique identifier for the team.

        Returns:
            Team: A Team object containing detailed team information.

        Raises:
            ApiError: If the team is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        resp = self._get(["team", _id])
        return self._validate_response(resp, Team)

    def team_post(self, data: TeamPost) -> TeamPostResponse:
        """Create a new team in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: TeamPost object containing the team information to create.

        Returns:
            TeamPostResponse: The newly created team response.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._handle_post_request(["team"], data, TeamPostResponse)

    def team_patch(self, _id: int, data: TeamPost) -> TeamPostResponse:
        """Update an existing team in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the team to update.
            data: TeamPost object containing the updated team information.

        Returns:
            TeamPostResponse: The updated team response.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._handle_patch_request(["team", _id], data, TeamPostResponse)

    def teams_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of teams with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing teams.
        """
        resp = self._get_results(["team"], params)
        return self._validate_list_response(resp, BaseResource)

    def team_issues_list(self, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues featuring a specific team.

        Args:
            _id: The unique identifier for the team.

        Returns:
            list[BaseIssue]: A list of BaseIssue objects representing issues featuring the team.
        """
        resp = self._get_results(["team", _id, "issue_list"])
        return self._validate_list_response(resp, BaseIssue)

    # Arc methods
    def arc(self, _id: int) -> Arc:
        """Retrieve detailed information about a story arc by ID.

        Args:
            _id: The unique identifier for the arc.

        Returns:
            Arc: An Arc object containing detailed arc information.

        Raises:
            ApiError: If the arc is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        resp = self._get(["arc", _id])
        return self._validate_response(resp, Arc)

    def arc_post(self, data: ArcPost) -> Arc:
        """Create a new story arc in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: ArcPost object containing the arc information to create.

        Returns:
            Arc: The newly created Arc object.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._handle_post_request(["arc"], data, Arc)

    def arc_patch(self, _id: int, data: ArcPost) -> Arc:
        """Update an existing story arc in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the arc to update.
            data: ArcPost object containing the updated arc information.

        Returns:
            Arc: The updated Arc object.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._handle_patch_request(["arc", _id], data, Arc)

    def arcs_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of story arcs with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing arcs.
        """
        resp = self._get_results(["arc"], params)
        return self._validate_list_response(resp, BaseResource)

    def arc_issues_list(self, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues that are part of a specific story arc.

        Args:
            _id: The unique identifier for the arc.

        Returns:
            list[BaseIssue]: A list of BaseIssue objects representing issues in the arc.
        """
        resp = self._get_results(["arc", _id, "issue_list"])
        return self._validate_list_response(resp, BaseIssue)

    # Series methods
    def series(self, _id: int) -> Series:
        """Retrieve detailed information about a series by ID.

        Args:
            _id: The unique identifier for the series.

        Returns:
            Series: A Series object containing detailed series information.

        Raises:
            ApiError: If the series is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        resp = self._get(["series", _id])
        return self._validate_response(resp, Series)

    def series_post(self, data: SeriesPost) -> SeriesPostResponse:
        """Create a new series in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: SeriesPost object containing the series information to create.

        Returns:
            SeriesPostResponse: The newly created series response.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._handle_post_request(["series"], data, SeriesPostResponse)

    def series_patch(self, _id: int, data: SeriesPost) -> SeriesPostResponse:
        """Update an existing series in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the series to update.
            data: SeriesPost object containing the updated series information.

        Returns:
            SeriesPostResponse: The updated series response.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._handle_patch_request(["series", _id], data, SeriesPostResponse)

    def series_list(self, params: dict[str, str | int] | None = None) -> list[BaseSeries]:
        """Retrieve a list of series with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'publisher', 'year_began', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseSeries]: A list of BaseSeries objects representing series.
        """
        resp = self._get_results(["series"], params)
        return self._validate_list_response(resp, BaseSeries)

    def series_type_list(self, params: dict[str, str | int] | None = None) -> list[GenericItem]:
        """Retrieve a list of available series types.

        Args:
            params: Optional dictionary of query parameters for filtering results.

        Returns:
            list[GenericItem]: A list of GenericItem objects representing series types.
        """
        resp = self._get_results(["series_type"], params)
        return self._validate_list_response(resp, GenericItem)

    # Issue methods
    def issue(self, _id: int) -> Issue:
        """Retrieve detailed information about an issue by ID.

        Args:
            _id: The unique identifier for the issue.

        Returns:
            Issue: An Issue object containing detailed issue information including
                  series, characters, credits, and other metadata.

        Raises:
            ApiError: If the issue is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("username", "password")
            >>> issue = session.issue(1)
            >>> print(f"Issue #{issue.number} of {issue.series.name}")
        """
        resp = self._get(["issue", _id])
        return self._validate_response(resp, Issue)

    def issue_post(self, data: IssuePost) -> IssuePostResponse:
        """Create a new issue in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: IssuePost object containing the issue information to create.

        Returns:
            IssuePostResponse: The newly created issue response.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._handle_post_request(["issue"], data, IssuePostResponse)

    def issue_patch(self, _id: int, data: IssuePost) -> IssuePostResponse:
        """Update an existing issue in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the issue to update.
            data: IssuePost object containing the updated issue information.

        Returns:
            IssuePostResponse: The updated issue response.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._handle_patch_request(["issue", _id], data, IssuePostResponse)

    def issues_list(self, params: dict[str, str | int] | None = None) -> list[BaseIssue]:
        """Retrieve a list of issues with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'series', 'number', 'cover_date', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseIssue]: A list of BaseIssue objects representing issues.

        Examples:
            >>> session = Session("username", "password")
            >>> issues = session.issues_list({"series": 1})
            >>> recent_issues = session.issues_list({"modified_gt": "2023-01-01"})
        """
        resp = self._get_results(["issue"], params)
        return self._validate_list_response(resp, BaseIssue)

    def credits_post(self, data: list[CreditPost]) -> list[CreditPostResponse]:
        """Create new credits for issues in bulk.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: List of CreditPost objects containing credit information to create.

        Returns:
            list[CreditPostResponse]: A list of newly created credit responses.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("username", "password")
            >>> credits_ = [CreditPost(issue=1, creator=1, role=[1])]
            >>> new_credits = session.credits_post(credits_)
        """
        return self._handle_post_request(["credit"], data, list[CreditPostResponse])

    def variant_post(self, data: VariantPost) -> VariantPostResponse:
        """Create a new variant cover for an issue.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: VariantPost object containing the variant cover information to create.

        Returns:
            VariantPostResponse: The newly created variant cover response.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._handle_post_request(["variant"], data, VariantPostResponse)

    def role_list(self, params: dict[str, str | int] | None = None) -> list[GenericItem]:
        """Retrieve a list of available creator roles.

        Args:
            params: Optional dictionary of query parameters for filtering results.

        Returns:
            list[GenericItem]: A list of GenericItem objects representing creator roles
                              (e.g., Writer, Artist, Colorist, etc.).
        """
        resp = self._get_results(["role"], params)
        return self._validate_list_response(resp, GenericItem)

    # Universe methods
    def universe(self, _id: int) -> Universe:
        """Retrieve detailed information about a universe by ID.

        Args:
            _id: The unique identifier for the universe.

        Returns:
            Universe: A Universe object containing detailed universe information.

        Raises:
            ApiError: If the universe is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        resp = self._get(["universe", _id])
        return self._validate_response(resp, Universe)

    def universe_post(self, data: UniversePost) -> UniversePostResponse:
        """Create a new universe in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: UniversePost object containing the universe information to create.

        Returns:
            UniversePostResponse: The newly created universe response.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._handle_post_request(["universe"], data, UniversePostResponse)

    def universe_patch(self, _id: int, data: UniversePost) -> UniversePostResponse:
        """Update an existing universe in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the universe to update.
            data: UniversePost object containing the updated universe information.

        Returns:
            UniversePostResponse: The updated universe response.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._handle_patch_request(["universe", _id], data, UniversePostResponse)

    def universes_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of universes with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing universes.
        """
        resp = self._get_results(["universe"], params)
        return self._validate_list_response(resp, BaseResource)

    # Imprint methods
    def imprint(self, _id: int) -> Imprint:
        """Retrieve detailed information about an imprint by ID.

        Args:
            _id: The unique identifier for the imprint.

        Returns:
            Imprint: An Imprint object containing detailed imprint information.

        Raises:
            ApiError: If the imprint is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        resp = self._get(["imprint", _id])
        return self._validate_response(resp, Imprint)

    def imprints_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of imprints with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'publisher', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing imprints.
        """
        resp = self._get_results(["imprint"], params)
        return self._validate_list_response(resp, BaseResource)

    def _get_results(
        self,
        endpoint: list[str | int],
        params: dict[str, str | int] | None = None,
    ) -> dict[str, Any]:
        """Retrieve results from the specified API endpoint with automatic pagination handling.

        This internal method handles paginated responses by automatically following 'next' links
        to retrieve all available results. It's used by list methods to ensure complete data retrieval.

        Args:
            endpoint: List of path segments to build the API endpoint URL.
            params: Optional query parameters to include in the request.

        Returns:
            dict[str, Any]: The complete response data with all paginated results combined.
        """
        if params is None:
            params = {}

        result = self._get(endpoint, params=params)
        if result["next"]:
            result = self._retrieve_all_results(result)
        return result

    def _retrieve_all_results(self, data: dict[str, Any]) -> dict[str, Any]:
        """Retrieve all results from paginated data by following 'next' links.

        This internal method handles the pagination logic by making additional requests
        to fetch all pages of results. It respects caching and rate limiting.

        Args:
            data: Dictionary containing the initial response data with pagination information.

        Returns:
            dict[str, Any]: Dictionary containing all results retrieved by following pagination links.
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
    def _request_data(  # noqa: C901
        self,
        method: str,
        url: str,
        params: dict[str, str | int] | None = None,
        data: T | None = None,
    ) -> Any:
        """Send an HTTP request to the API with comprehensive error handling.

        This internal method handles all HTTP communication with the Metron API, including
        authentication, rate limiting, error handling, and response parsing. It supports
        both simple data requests and file uploads.

        Args:
            method: HTTP method to use ("GET", "POST", "PATCH").
            url: The complete URL to send the request to.
            params: Optional query parameters to include in the request.
            data: Optional data to include in the request body.

        Returns:
            Any: The parsed JSON response from the API.

        Raises:
            ApiError: For connection errors, HTTP errors, or invalid JSON responses.
            RateLimitError: When the API rate limit is exceeded.

        Notes:
            - Automatically handles image file uploads when 'image' field is present in data
            - Implements exponential backoff for rate limiting
            - Supports both single objects and lists of objects for POST requests
        """
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
        ) as err:
            msg = f"Connection error: {err!r}"
            raise exceptions.ApiError(msg) from err

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == requests.codes.too_many:
                msg = f"Metron API Rate Limit exceeded, need to wait for {format_time(response.headers['Retry-After'])}."
                raise exceptions.RateLimitError(msg) from err
            msg = f"HTTP error: {err!r}"
            raise exceptions.ApiError(msg) from err

        try:
            resp = response.json()
        except ValueError as err:
            msg = f"Invalid JSON response: {err!r}"
            raise exceptions.ApiError(msg) from err

        if "detail" in resp:
            raise exceptions.ApiError(resp["detail"])

        return resp

    def _get_results_from_cache(self, key: str) -> Any | None:
        """Retrieve cached response data using the specified key.

        This internal method provides a safe interface to the cache system with
        proper error handling for missing cache methods.

        Args:
            key: The cache key to retrieve data for.

        Returns:
            Any | None: The cached response data if available and cache is configured,
                       None if not found or cache is not available.

        Raises:
            CacheError: If the cache object is missing required methods.
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

        This internal method provides a safe interface to the cache system with
        proper error handling for missing cache methods.

        Args:
            key: The cache key to store the data under.
            data: The data to be stored in the cache.

        Raises:
            CacheError: If the cache object is missing required methods.
        """
        if not self.cache:
            return

        try:
            self.cache.store(key, data)
        except AttributeError as e:
            msg = f"Cache object passed in is missing attribute: {e!r}"
            raise exceptions.CacheError(msg) from e

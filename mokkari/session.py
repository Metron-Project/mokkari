# ruff: noqa: TRY003, EM102
"""Session module.

This module provides the following classes:

- Session
"""

from __future__ import annotations

import platform
from collections import OrderedDict
from typing import Any
from urllib.parse import urlencode

import requests
from pydantic import TypeAdapter, ValidationError
from ratelimit import limits, sleep_and_retry
from requests.adapters import HTTPAdapter
from urllib3 import Retry

# Alias these modules to prevent namespace collision with methods.
from mokkari import __version__, exceptions, sqlite_cache
from mokkari.schemas.arc import Arc
from mokkari.schemas.base import BaseResource
from mokkari.schemas.character import Character
from mokkari.schemas.creator import Creator
from mokkari.schemas.generic import GenericItem
from mokkari.schemas.imprint import Imprint
from mokkari.schemas.issue import BaseIssue, Issue
from mokkari.schemas.publisher import Publisher
from mokkari.schemas.series import BaseSeries, Series
from mokkari.schemas.team import Team
from mokkari.schemas.universe import Universe

ONE_MINUTE = 60


class Session:
    """A class representing a Session for interacting with the API.

    Args:
        username: A string representing the username for authentication.
        passwd: A string representing the password for authentication.
        cache: An optional SqliteCache object for caching data.
        user_agent: An optional string representing the user agent for the session.
    """

    def __init__(
        self: Session,
        username: str,
        passwd: str,
        cache: sqlite_cache.SqliteCache | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Initialize a Session object with the provided username, password, cache, and user agent."""
        self.username = username
        self.passwd = passwd
        self.header = {
            "User-Agent": f"{f'{user_agent} ' if user_agent is not None else ''}"
            f"Mokkari/{__version__} ({platform.system()}; {platform.release()})"
        }
        self.api_url = "https://metron.cloud/api/{}/"
        self.cache = cache

    def _call(
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

        data = self._request_data(url, params)

        if "detail" in data:
            raise exceptions.ApiError(data["detail"])

        self._save_results_to_cache(cache_key, data)

        return data

    def creator(self: Session, _id: int) -> Creator:
        """Retrieve information about a creator with the specified ID.

        Args:
            _id: An integer representing the ID of the creator.

        Returns:
            A Creator object containing information about the specified creator.

        Raises:
            ValidationError: If there is an error validating the response data.
        """
        resp = self._call(["creator", _id])
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
        resp = self._call(["character", _id])
        adaptor = TypeAdapter(Character)
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
        resp = self._call(["publisher", _id])
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
        resp = self._call(["team", _id])
        adaptor = TypeAdapter(Team)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def teams_list(
        self: Session, params: dict[str, str | int] | None = None
    ) -> list[BaseResource]:
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
        resp = self._call(["arc", _id])
        adaptor = TypeAdapter(Arc)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def arcs_list(
        self: Session, params: dict[str, str | int] | None = None
    ) -> list[BaseResource]:
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
        resp = self._call(["series", _id])
        adaptor = TypeAdapter(Series)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def series_list(
        self: Session, params: dict[str, str | int] | None = None
    ) -> list[BaseSeries]:
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
        resp = self._call(["issue", _id])
        adaptor = TypeAdapter(Issue)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def issues_list(
        self: Session, params: dict[str, str | int] | None = None
    ) -> list[BaseIssue]:
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

    def role_list(
        self: Session, params: dict[str, str | int] | None = None
    ) -> list[GenericItem]:
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
        resp = self._call(["universe", _id])
        adaptor = TypeAdapter(Universe)
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
        resp = self._call(["imprint", _id])
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

        result = self._call(endpoint, params=params)
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

            response = self._request_data(next_page)
            data["results"].extend(response["results"])

            self._save_results_to_cache(next_page, response)

            if response["next"]:
                next_page = response["next"]
            else:
                has_next_page = False

        return data

    @sleep_and_retry
    @limits(calls=25, period=ONE_MINUTE)
    def _request_data(
        self: Session, url: str, params: dict[str, str | int] | None = None
    ) -> Any:
        """Send a request to the specified URL with optional parameters and handles retries.

        Args:
            url: A string representing the URL to send the request to.
            params: An optional dictionary of parameters to include in the request.

        Returns:
            The JSON response data from the request.

        Raises:
            ApiError: If there is a connection error during the request.
        """
        if params is None:
            params = {}

        try:
            session = requests.Session()
            retry = Retry(connect=3, backoff_factor=0.5)
            session.mount("https://", HTTPAdapter(max_retries=retry))
            response = session.get(
                url,
                params=params,
                timeout=2.5,
                auth=(self.username, self.passwd),
                headers=self.header,
            ).json()
        except requests.exceptions.ConnectionError as e:
            raise exceptions.ApiError(f"Connection error: {e!r}") from e

        return response

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

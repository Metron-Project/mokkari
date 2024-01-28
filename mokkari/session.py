"""
Session module.

This module provides the following classes:

- Session
"""

import platform
from collections import OrderedDict
from typing import Any, Optional, Union
from urllib.parse import urlencode

import requests
from pydantic import TypeAdapter, ValidationError
from ratelimit import limits, sleep_and_retry
from requests.adapters import HTTPAdapter
from urllib3 import Retry

# Alias these modules to prevent namespace collision with methods.
from mokkari import __version__, exceptions, sqlite_cache
from mokkari.schemas.arc import Arc, BaseArc
from mokkari.schemas.character import BaseCharacter, Character
from mokkari.schemas.creator import BaseCreator, Creator
from mokkari.schemas.generic import GenericItem
from mokkari.schemas.issue import BaseIssue, Issue
from mokkari.schemas.publisher import BasePublisher, Publisher
from mokkari.schemas.series import BaseSeries, Series
from mokkari.schemas.team import BaseTeam, Team
from mokkari.schemas.universe import Universe, BaseUniverse

ONE_MINUTE = 60


class Session:
    """
    Session to request api endpoints.

    Args:
        username (str): The username for authentication with metron.cloud
        passwd (str): The password used for authentication with metron.cloud
        cache (SqliteCache, optional): SqliteCache to use
        user_agent optional(str): The user agent string for the application using Mokkari.
    """

    def __init__(
        self,
        username: str,
        passwd: str,
        cache: Optional[sqlite_cache.SqliteCache] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Initialize a new Session."""
        self.username = username
        self.passwd = passwd
        self.header = {
            "User-Agent": f"{f'{user_agent} ' if user_agent is not None else ''}"
            + f"Mokkari/{__version__} ({platform.system()}; {platform.release()})"
        }
        self.api_url = "https://metron.cloud/api/{}/"
        self.cache = cache

    def _call(
        self,
        endpoint: list[Union[str, int]],
        params: Optional[dict[str, Union[str, int]]] = None,
    ) -> dict[str, Any]:
        """
        Make request for api endpoints.

        Args:
            endpoint (str): The endpoint to request information from.
            params (dict[str, any]): Parameters to add to the request.
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

    def creator(self, _id: int) -> Creator:
        """
        Request data for a creator based on its ``_id``.

        Args:
            _id (int): The creator id.

        Returns:
            A :obj:`Creator` object.

        Raises:
            ApiError: If there is a problem with the API request.
        """
        resp = self._call(["creator", _id])
        adaptor = TypeAdapter(Creator)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def creators_list(
        self, params: Optional[dict[str, Union[str, int]]] = None
    ) -> list[BaseCreator]:
        """
        Request a list of creators.

        Args:
            params (dict, optional): Parameters to add to the request.

        Returns:
            A :obj:`CreatorsList` object.
        """
        resp = self._get_results(["creator"], params)
        adaptor = TypeAdapter(list[BaseCreator])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def character(self, _id: int) -> Character:
        """
        Request data for a character based on its ``_id``.

        Args:
            _id (int): The character id.

        Returns:
            A :obj:`Character` object.

        Raises:
            ApiError: If there is a problem with the API request.
        """
        resp = self._call(["character", _id])
        adaptor = TypeAdapter(Character)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def characters_list(
        self, params: Optional[dict[str, Union[str, int]]] = None
    ) -> list[BaseCharacter]:
        """
        Request a list of characters.

        Args:
            params (dict, optional): Parameters to add to the request.

        Returns:
            A :class:`CharactersList` object.
        """
        resp = self._get_results(["character"], params)
        adaptor = TypeAdapter(list[BaseCharacter])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def character_issues_list(self, _id: int) -> list[BaseIssue]:
        """
        Request a list of issues that a character appears in.

        .. versionadded:: 2.2.0

        Args:
            _id (int): The character id.

        Returns:
            A list of :class:`Issue` objects.
        """
        resp = self._get_results(["character", _id, "issue_list"])
        adaptor = TypeAdapter(list[BaseIssue])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def publisher(self, _id: int) -> Publisher:
        """
        Request data for a publisher based on its ``_id``.

        Args:
            _id (int): The publisher id.

        Returns:
            A :obj:`Publisher` object.

        Raises:
            ApiError: If there is a problem with the API request.
        """
        resp = self._call(["publisher", _id])
        adaptor = TypeAdapter(Publisher)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def publishers_list(
        self, params: Optional[dict[str, Union[str, int]]] = None
    ) -> list[BasePublisher]:
        """
        Request a list of publishers.

        Args:
            params (dict, optional): Parameters to add to the request.

        Returns:
            A :class:`PublishersList` object.
        """
        resp = self._get_results(["publisher"], params)
        adapter = TypeAdapter(list[BasePublisher])
        try:
            result = adapter.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def team(self, _id: int) -> Team:
        """
        Request data for a team based on its ``_id``.

        Args:
            _id (int): The team id.

        Returns:
            A :obj:`Team` object.

        Raises:
            ApiError: If there is a problem with the API request.
        """
        resp = self._call(["team", _id])
        adaptor = TypeAdapter(Team)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def teams_list(self, params: Optional[dict[str, Union[str, int]]] = None) -> list[BaseTeam]:
        """
        Request a list of teams.

        Args:
            params (dict, optional): Parameters to add to the request.

        Returns:
            A :class:`TeamsList` object.
        """
        resp = self._get_results(["team"], params)
        adapter = TypeAdapter(list[BaseTeam])
        try:
            result = adapter.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def team_issues_list(self, _id: int) -> list[BaseIssue]:
        """
        Request a list of issues that a team appears in.

        .. versionadded:: 2.2.0

        Args:
            _id (int): The team id.

        Returns:
            A list of :class:`Issue` objects.
        """
        resp = self._get_results(["team", _id, "issue_list"])
        adapter = TypeAdapter(list[BaseIssue])
        try:
            result = adapter.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def arc(self, _id: int) -> Arc:
        """
        Request data for a story arc based on its ``_id``.

        Args:
            _id (int): The story arc id.

        Returns:
            A :obj:`Arc` object.

        Raises:
            ApiError: If there is a problem with the API request.
        """
        resp = self._call(["arc", _id])
        adaptor = TypeAdapter(Arc)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def arcs_list(self, params: Optional[dict[str, Union[str, int]]] = None) -> list[BaseArc]:
        """
        Request a list of story arcs.

        Args:
            params (dict, optional): Parameters to add to the request.

        Returns:
            A :class:`ArcsList` object.
        """
        resp = self._get_results(["arc"], params)
        adapter = TypeAdapter(list[BaseArc])
        try:
            result = adapter.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def arc_issues_list(self, _id: int) -> list[BaseIssue]:
        """
        Request a list of issues for a story arc.

        Args:
            _id (int): The arc id.

        Returns:
            A list of :class:`Issue` objects.
        """
        resp = self._get_results(["arc", _id, "issue_list"])
        adaptor = TypeAdapter(list[BaseIssue])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def series(self, _id: int) -> Series:
        """
        Request data for a series based on its ``_id``.

        Args:
            _id (int): The series id.

        Returns:
            A :obj:`Series` object.

        Raises:
            ApiError: If there is a problem with the API request.
        """
        resp = self._call(["series", _id])
        adaptor = TypeAdapter(Series)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def series_list(self, params: Optional[dict[str, Union[str, int]]] = None) -> list[BaseSeries]:
        """
        Request a list of series.

        Args:
            params (dict, optional): Parameters to add to the request.

        Returns:
            A :class:`SeriesList` object.
        """
        resp = self._get_results(["series"], params)
        adaptor = TypeAdapter(list[BaseSeries])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def series_type_list(
        self, params: Optional[dict[str, Union[str, int]]] = None
    ) -> list[GenericItem]:
        """
        Request a list of series types.

        .. versionadded:: 2.2.2

            - Add ``series_type_list`` method

        Args:
            params (dict, optional): Parameters to add to the request.

        Returns:
            A :class:`SeriesTypeList` object.
        """
        resp = self._get_results(["series_type"], params)
        adaptor = TypeAdapter(list[GenericItem])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def issue(self, _id: int) -> Issue:
        """
        Request data for an issue based on it's ``_id``.

        Args:
            _id (int): The issue id.

        Returns:
            A :obj:`Issue` object.

        Raises:
            ApiError: If there is a problem with the API request.
        """
        resp = self._call(["issue", _id])
        adaptor = TypeAdapter(Issue)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def issues_list(self, params: Optional[dict[str, Union[str, int]]] = None) -> list[BaseIssue]:
        """
        Request a list of issues.

        Args:
            params (dict, optional): Parameters to add to the request.

        Returns:
            A :class:`IssuesList` object.
        """
        resp = self._get_results(["issue"], params)
        adaptor = TypeAdapter(list[BaseIssue])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def role_list(self, params: Optional[dict[str, Union[str, int]]] = None) -> list[GenericItem]:
        """
        Request a list of creator roles.

        Args:
            params (dict, optional): Parameters to add to the request.

        Returns:
            A :class:`RoleList` object.

        """
        resp = self._get_results(["role"], params)
        adaptor = TypeAdapter(list[GenericItem])
        try:
            result = adaptor.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def universe(self, _id: int) -> Universe:
        """
        Request data for a universe based on its ``_id``.

        Args:
            _id (int): The universe id.

        Returns:
            A :obj:`Universe` object.

        Raises:
            ApiError: If there is a problem with the API request.
        """
        resp = self._call(["universe", _id])
        adaptor = TypeAdapter(Universe)
        try:
            result = adaptor.validate_python(resp)
        except ValidationError as error:
            raise exceptions.ApiError(error) from error
        return result

    def universes_list(self, params: Optional[dict[str, Union[str, int]]] = None) -> list[BaseUniverse]:
        """
        Request a list of universes.

        Args:
            params (dict, optional): Parameters to add to the request.

        Returns:
            A list of :class:`BaseUniverse` objects.
        """
        resp = self._get_results(["universe"], params)
        adapter = TypeAdapter(list[BaseUniverse])
        try:
            result = adapter.validate_python(resp["results"])
        except ValidationError as err:
            raise exceptions.ApiError(err) from err
        return result

    def _get_results(
        self,
        endpoint: list[Union[str, int]],
        params: Optional[dict[str, Union[str, int]]] = None,
    ) -> dict[str, Any]:
        if params is None:
            params = {}

        result = self._call(endpoint, params=params)
        if result["next"]:
            result = self._retrieve_all_results(result)
        return result

    def _retrieve_all_results(self, data: dict[str, Any]) -> dict[str, Any]:
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
    def _request_data(self, url: str, params: Optional[dict[str, Union[str, int]]] = None) -> Any:
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
            raise exceptions.ApiError(f"Connection error: {repr(e)}") from e

        return response

    def _get_results_from_cache(self, key: str) -> Optional[Any]:
        cached_response = None

        if self.cache:
            try:
                cached_response = self.cache.get(key)
            except AttributeError as e:
                raise exceptions.CacheError(
                    f"Cache object passed in is missing attribute: {repr(e)}"
                ) from e

        return cached_response

    def _save_results_to_cache(self, key: str, data: str) -> None:
        if self.cache:
            try:
                self.cache.store(key, data)
            except AttributeError as e:
                raise exceptions.CacheError(
                    f"Cache object passed in is missing attribute: {repr(e)}"
                ) from e

"""
Session module.

This module provides the following classes:

- Session
"""
import platform
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode

import requests
from marshmallow import ValidationError
from ratelimit import limits, sleep_and_retry
from requests.adapters import HTTPAdapter
from urllib3 import Retry

# Alias these modules to prevent namespace collision with methods.
from mokkari import __version__
from mokkari import arc as arcs
from mokkari import character as characters
from mokkari import creator as creators
from mokkari import exceptions
from mokkari import issue as issues
from mokkari import publisher as publishers
from mokkari import series as ser
from mokkari import sqlite_cache
from mokkari import team as teams

ONE_MINUTE = 60


class Session:
    """
    Session to request api endpoints.

    :param str username: The username for authentication with metron.cloud
    :param str passwd: The password used for authentication with metron.cloud
    :param SqliteCache optional: SqliteCache to use
    """

    def __init__(
        self,
        username: str,
        passwd: str,
        cache: Optional[sqlite_cache.SqliteCache] = None,
    ) -> None:
        """Intialize a new Session."""
        self.username = username
        self.passwd = passwd
        self.header = {
            "User-Agent": f"Mokkari/{__version__} ({platform.system()}; {platform.release()})"
        }
        self.api_url = "https://metron.cloud/api/{}/"
        self.cache = cache

    def _call(
        self, endpoint: List[Union[str, int]], params: Dict[str, Union[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Make request for api endpoints.

        :param str endpoint: The endpoint to request information from.
        :param dict params: Parameters to add to the request.
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

    def creator(self, _id: int) -> creators.Creator:
        """
        Request data for a creator based on its ``_id``.

        :param int _id: The creator id.

        :return: :class:`Creator` object
        :rtype: Creator

        :raises: :class:`ApiError`
        """
        try:
            result = creators.CreatorSchema().load(self._call(["creator", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error) from error

        return result

    def creators_list(
        self, params: Optional[Dict[str, Union[str, int]]] = None
    ) -> creators.CreatorsList:
        """
        Request a list of creators.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Creator` objects containing their id and name.
        :rtype: CreatorsList
        """
        res = self._get_results("creator", params)
        return creators.CreatorsList(res)

    def character(self, _id: int) -> characters.Character:
        """
        Request data for a character based on its ``_id``.

        :param int _id: The character id.

        :return: :class:`Character` object
        :rtype: Character

        :raises: :class:`ApiError`
        """
        try:
            result = characters.CharacterSchema().load(self._call(["character", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error) from error

        return result

    def characters_list(
        self, params: Optional[Dict[str, Union[str, int]]] = None
    ) -> characters.CharactersList:
        """
        Request a list of characters.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Character` objects containing their id and name.
        :rtype: CharactersList
        """
        res = self._get_results("character", params)
        return characters.CharactersList(res)

    def publisher(self, _id: int) -> publishers.Publisher:
        """
        Request data for a publisher based on its ``_id``.

        :param int _id: The publisher id.

        :return: :class:`Publisher` object
        :rtype: Publisher

        :raises: :class:`ApiError`
        """
        try:
            result = publishers.PublisherSchema().load(self._call(["publisher", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error) from error

        return result

    def publishers_list(
        self, params: Dict[str, Union[str, int]] = None
    ) -> publishers.PublishersList:
        """
        Request a list of publishers.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Publisher` objects containing their id and name.
        :rtype: PublishersList
        """
        res = self._get_results("publisher", params)
        return publishers.PublishersList(res)

    def team(self, _id: int) -> teams.Team:
        """
        Request data for a team based on its ``_id``.

        :param int _id: The team id.

        :return: :class:`Team` object
        :rtype: Team

        :raises: :class:`ApiError`
        """
        try:
            result = teams.TeamSchema().load(self._call(["team", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error) from error

        return result

    def teams_list(self, params: Dict[str, Union[str, int]] = None) -> teams.TeamsList:
        """
        Request a list of teams.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Team` objects containing their id and name.
        :rtype: TeamsList
        """
        res = self._get_results("team", params)
        return teams.TeamsList(res)

    def arc(self, _id: int) -> arcs.Arc:
        """
        Request data for a story arc based on its ``_id``.

        :param int _id: The story arc id.

        :return: :class:`Arc` object
        :rtype: Arc

        :raises: :class:`ApiError`
        """
        try:
            result = arcs.ArcSchema().load(self._call(["arc", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error) from error

        return result

    def arcs_list(self, params: Dict[str, Union[str, int]] = None) -> arcs.ArcsList:
        """
        Request a list of story arcs.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Arc` objects containing their id and name.
        :rtype: ArcsList
        """
        res = self._get_results("arc", params)
        return arcs.ArcsList(res)

    def series(self, _id: int) -> ser.Series:
        """
        Request data for a series based on its ``_id``.

        :param int _id: The series id.

        :return: :class:`Series` object
        :rtype: Series

        :raises: :class:`ApiError`
        """
        try:
            result = ser.SeriesSchema().load(self._call(["series", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error) from error

        return result

    def series_list(self, params: Dict[str, Union[str, int]] = None) -> ser.SeriesList:
        """
        Request a list of series.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Series` objects containing their id and name.
        :rtype: SeriesList
        """
        res = self._get_results("series", params)
        return ser.SeriesList(res)

    def issue(self, _id: int) -> issues.Issue:
        """
        Request data for an issue based on it's ``_id``.

        :param int _id: The issue id.

        :return: :class:`Issue` object
        :rtype: Issue

        :raises: :class:`ApiError`
        """
        try:
            result = issues.IssueSchema().load(self._call(["issue", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error) from error

        return result

    def issues_list(self, params: Dict[str, Union[str, int]] = None) -> issues.IssuesList:
        """
        Request a list of issues.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Issue` objects containing their id and name.
        :rtype: IssuesList
        """
        res = self._get_results("issue", params)
        return issues.IssuesList(res)

    def role_list(self, params: Dict[str, Union[str, int]] = None) -> issues.RoleList:
        """
        Request a list of creator roles.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Role` objects containing their id and name.
        :rtype: RoleList

        """
        res = self._get_results("role", params)
        return issues.RoleList(res)

    def _get_results(
        self, resource: str, params: Optional[Dict[str, Union[str, int]]]
    ) -> Dict[str, Any]:
        if params is None:
            params = {}

        result = self._call([resource], params=params)
        if result["next"]:
            result = self._retrieve_all_results(result)
        return result

    def _retrieve_all_results(self, data: Dict[str, Any]) -> Dict[str, Any]:
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
        self, url: str, params: Optional[Dict[str, Union[str, int]]] = None
    ) -> Any:
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

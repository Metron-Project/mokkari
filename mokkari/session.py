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

from mokkari import (
    __version__,
    arc,
    arcs_list,
    character,
    characters_list,
    creator,
    creators_list,
    exceptions,
    issue,
    issues_list,
    publisher,
    publishers_list,
    series,
    series_list,
    sqlite_cache,
    team,
    teams_list,
)

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

    def call(
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

    def creator(self, _id: int) -> creator.Creator:
        """
        Request data for a creator based on its ``_id``.

        :param int _id: The creator id.

        :return: :class:`Creator` object
        :rtype: Creator
        """
        try:
            result = creator.CreatorSchema().load(self.call(["creator", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        return result

    def creators_list(self, name: Optional[str] = None, page: Optional[int] = None):
        """
        Request a list of creators.

        :param name: Name of creator to search for.
        :type name: str, optional

        :param page: A page number within the paginated result set.
        :type page: int, optional

        :return: A list of :class:`Creator` objects containing their id and name.
        :rtype: CreatorsList
        """
        params = {}
        if name:
            params["name"] = name
        if page:
            params["page"] = page
        res = self._get_results("creator", params)
        return creators_list.CreatorsList(res)

    def character(self, _id: int) -> character.Character:
        """
        Request data for a character based on its ``_id``.

        :param int _id: The character id.

        :return: :class:`Character` object
        :rtype: Character
        """
        try:
            result = character.CharacterSchema().load(self.call(["character", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        return result

    def characters_list(self, name: Optional[str] = None, page: Optional[int] = None):
        """
        Request a list of characters.

        :param name: Name of character to search for.
        :type name: str, optional

        :param page: A page number within the paginated result set.
        :type page: int, optional

        :return: A list of :class:`Character` objects containing their id and name.
        :rtype: CharactersList
        """
        params = {}
        if name:
            params["name"] = name
        if page:
            params["page"] = page
        res = self._get_results("character", params)
        return characters_list.CharactersList(res)

    def publisher(self, _id: int) -> publisher.Publisher:
        """
        Request data for a publisher based on its ``_id``.

        :param int _id: The publisher id.

        :return: :class:`Publisher` object
        :rtype: Publisher
        """
        try:
            result = publisher.PublisherSchema().load(self.call(["publisher", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        return result

    def publishers_list(self, name: Optional[str] = None, page: Optional[int] = None):
        """
        Request a list of publishers.

        :param name: Name of the publisher to search for.
        :type name: str, optional

        :param page: A page number within the paginated result set.
        :type page: int, optional

        :return: A list of :class:`Publisher` objects containing their id and name.
        :rtype: PublishersList
        """
        params = {}
        if name:
            params["name"] = name
        if page:
            params["page"] = page
        res = self._get_results("publisher", params)
        return publishers_list.PublishersList(res)

    def team(self, _id: int) -> team.Team:
        """
        Request data for a team based on its ``_id``.

        :param int _id: The team id.

        :return: :class:`Team` object
        :rtype: Team
        """
        try:
            result = team.TeamSchema().load(self.call(["team", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        return result

    def teams_list(self, name: Optional[str] = None, page: Optional[int] = None):
        """
        Request a list of teams.

        :param name: Name of the team to search for.
        :type name: str, optional

        :param page: A page number within the paginated result set.
        :type page: int, optional

        :return: A list of :class:`Team` objects containing their id and name.
        :rtype: TeamsList
        """
        params = {}
        if name:
            params["name"] = name
        if page:
            params["page"] = page
        res = self._get_results("team", params)
        return teams_list.TeamsList(res)

    def arc(self, _id: int) -> arc.Arc:
        """
        Request data for a story arc based on its ``_id``.

        :param int _id: The story arc id.

        :return: :class:`Arc` object
        :rtype: Arc
        """
        try:
            result = arc.ArcSchema().load(self.call(["arc", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        return result

    def arcs_list(self, name: Optional[str] = None, page: Optional[int] = None):
        """
        Request a list of story arcs.

        :param name: Name of the arc to search for.
        :type name: str, optional

        :param page: A page number within the paginated result set.
        :type page: int, optional

        :return: A list of :class:`Arc` objects containing their id and name.
        :rtype: ArcsList
        """
        params = {}
        if name:
            params["name"] = name
        if page:
            params["page"] = page
        res = self._get_results("arc", params)
        return arcs_list.ArcsList(res)

    def series(self, _id: int) -> series.Series:
        """
        Request data for a series based on its ``_id``.

        :param int _id: The series id.

        :return: :class:`Series` object
        :rtype: Series
        """
        try:
            result = series.SeriesSchema().load(self.call(["series", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        return result

    def series_list(self, params: Dict[str, Union[str, int]] = None):
        """
        Request a list of series.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Series` objects containing their id and name.
        :rtype: SeriesList
        """
        res = self._get_results("series", params)
        return series_list.SeriesList(res)

    def issue(self, _id: int) -> issue.Issue:
        """
        Request data for an issue based on it's ``_id``.

        :param int _id: The issue id.

        :return: :class:`Issue` object
        :rtype: Issue
        """
        try:
            result = issue.IssueSchema().load(self.call(["issue", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        return result

    def issues_list(self, params: Dict[str, Union[str, int]] = None):
        """
        Request a list of issues.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Issue` objects containing their id and name.
        :rtype: IssuesList
        """
        res = self._get_results("issue", params)
        return issues_list.IssuesList(res)

    def _get_results(
        self, resource: str, params: Optional[Dict[str, Union[str, int]]]
    ) -> Dict[str, Any]:
        if params is None:
            params = {}

        result = self.call([resource], params=params)
        if result["next"]:
            result = self._retrieve_all_results(result)
        return result

    def _retrieve_all_results(self, data):
        has_next_page = True
        next_page = data["next"]

        while has_next_page:
            cached_response = self._get_results_from_cache(next_page)
            if cached_response:
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
    @limits(calls=20, period=ONE_MINUTE)
    def _request_data(
        self, url: str, params: Optional[Dict[str, Union[str, int]]] = None
    ) -> Any:
        if params is None:
            params = {}

        try:
            response = requests.get(
                url,
                params=params,
                auth=(self.username, self.passwd),
                headers=self.header,
            ).json()
        except requests.exceptions.ConnectionError as e:
            raise exceptions.ApiError(f"Connection error: {repr(e)}")

        return response

    def _get_results_from_cache(self, key: str) -> Optional[Any]:
        cached_response = None

        if self.cache:
            try:
                cached_response = self.cache.get(key)
            except AttributeError as e:
                raise exceptions.CacheError(
                    f"Cache object passed in is missing attribute: {repr(e)}"
                )

        return cached_response

    def _save_results_to_cache(self, key: str, data: str) -> None:
        if self.cache:
            try:
                self.cache.store(key, data)
            except AttributeError as e:
                raise exceptions.CacheError(
                    f"Cache object passed in is missing attribute: {repr(e)}"
                )

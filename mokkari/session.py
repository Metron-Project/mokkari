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
    Session to request api endpoints

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
        self.username = username
        self.passwd = passwd
        self.header = {
            "User-Agent": f"Mokkari/{__version__} ({platform.system()}; {platform.release()})"
        }
        self.api_url = "https://metron.cloud/api/{}/"
        self.cache = cache

    @sleep_and_retry
    @limits(calls=20, period=ONE_MINUTE)
    def call(
        self, endpoint: List[Union[str, int]], params: Dict[str, Union[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Method to make request for api endpoints.

        :param str endpoint: The endpoint to request information from.
        :param dict params: Parameters to add to the request.
        """
        if params is None:
            params = {}

        cache_params = ""
        if params:
            ordered_params = OrderedDict(sorted(params.items(), key=lambda t: t[0]))
            cache_params = "?{}".format(urlencode(ordered_params))

        url = self.api_url.format("/".join(str(e) for e in endpoint))
        cache_key = f"{url}{cache_params}"

        if self.cache:
            try:
                cached_response = self.cache.get(cache_key)

                if cached_response is not None:
                    return cached_response
            except AttributeError as e:
                raise exceptions.CacheError(
                    "Cache object passed in is missing attribute: {}".format(repr(e))
                )

        try:
            response = requests.get(
                url,
                params=params,
                auth=(self.username, self.passwd),
                headers=self.header,
            )
        except requests.exceptions.ConnectionError as e:
            raise exceptions.ApiError("Connection error: {}".format(repr(e)))

        data = response.json()

        if "detail" in data:
            raise exceptions.ApiError(data["detail"])

        if self.cache:
            try:
                self.cache.store(cache_key, data)
            except AttributeError as e:
                raise exceptions.CacheError(
                    "Cache object passed in is missing attribute: {}".format(repr(e))
                )

        return data

    def creator(self, _id: int) -> creator.Creator:
        """
        Method to request data for a creator based on its ``_id``.

        :param int _id: The creator id.

        :return: :class:`Creator` object
        :rtype: Creator
        """
        try:
            result = creator.CreatorSchema().load(self.call(["creator", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def creators_list(self, params: Optional[Dict[str, Union[str, int]]] = None):
        """
        Method to request a list of creators.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Creator` objects containing their id and name.
        :rtype: CreatorsList
        """
        if params is None:
            params = {}
        return creators_list.CreatorsList(self.call(["creator"], params=params))

    def character(self, _id: int) -> character.Character:
        """
        Method to request data for a character based on its ``_id``.

        :param int _id: The character id.

        :return: :class:`Character` object
        :rtype: Character
        """
        try:
            result = character.CharacterSchema().load(self.call(["character", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def characters_list(self, params: Optional[Dict[str, Union[str, int]]] = None):
        """
        Method to request a list of characters.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Character` objects containing their id and name.
        :rtype: CharactersList
        """
        if params is None:
            params = {}
        return characters_list.CharactersList(self.call(["character"], params=params))

    def publisher(self, _id: int) -> publisher.Publisher:
        """
        Method to request data for a publisher based on its ``_id``.

        :param int _id: The publisher id.

        :return: :class:`Publisher` object
        :rtype: Publisher
        """
        try:
            result = publisher.PublisherSchema().load(self.call(["publisher", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def publishers_list(self, params: Dict[str, Union[str, int]] = None):
        """
        Method to request a list of publishers.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Publisher` objects containing their id and name.
        :rtype: PublishersList
        """
        if params is None:
            params = {}
        return publishers_list.PublishersList(self.call(["publisher"], params=params))

    def team(self, _id: int) -> team.Team:
        """
        Method to request data for a team based on its ``_id``.

        :param int _id: The team id.

        :return: :class:`Team` object
        :rtype: Team
        """
        try:
            result = team.TeamSchema().load(self.call(["team", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def teams_list(self, params: Dict[str, Union[str, int]] = None):
        """
        Method to request a list of teams.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Team` objects containing their id and name.
        :rtype: TeamsList
        """
        if params is None:
            params = {}
        return teams_list.TeamsList(self.call(["team"], params=params))

    def arc(self, _id: int) -> arc.Arc:
        """
        Method to request data for a story arc based on its ``_id``.

        :param int _id: The story arc id.

        :return: :class:`Arc` object
        :rtype: Arc
        """
        try:
            result = arc.ArcSchema().load(self.call(["arc", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def arcs_list(self, params: Dict[str, Union[str, int]] = None):
        """
        Method to request a list of story arcs.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Arc` objects containing their id and name.
        :rtype: ArcsList
        """
        if params is None:
            params = {}
        return arcs_list.ArcsList(self.call(["arc"], params=params))

    def series(self, _id: int) -> series.Series:
        """
        Method to request data for a series based on its ``_id``.

        :param int _id: The series id.

        :return: :class:`Series` object
        :rtype: Series
        """
        try:
            result = series.SeriesSchema().load(self.call(["series", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def series_list(self, params: Dict[str, Union[str, int]] = None):
        """
        Method to request a list of series.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Series` objects containing their id and name.
        :rtype: SeriesList
        """
        if params is None:
            params = {}
        return series_list.SeriesList(self.call(["series"], params=params))

    def issue(self, _id: int) -> issue.Issue:
        """
        Method to request data for an issue based on it's ``_id``.

        :param int _id: The issue id.

        :return: :class:`Issue` object
        :rtype: Issue
        """
        try:
            result = issue.IssueSchema().load(self.call(["issue", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def issues_list(self, params: Dict[str, Union[str, int]] = None):
        """
        Method to request a list of issues.

        :param params: Parameters to add to the request.
        :type params: dict, optional

        :return: A list of :class:`Issue` objects containing their id and name.
        :rtype: IssuesList
        """
        if params is None:
            params = {}
        return issues_list.IssuesList(self.call(["issue"], params=params))

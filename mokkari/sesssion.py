import platform

import requests
from marshmallow import ValidationError
from ratelimit import limits, sleep_and_retry

from mokkari import (
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
    team,
    teams_list,
)

ONE_MINUTE = 60


class Session:
    def __init__(self, username, passwd) -> None:
        self.username = username
        self.passwd = passwd
        self.header = {
            "User-Agent": f"Mokkari/0.0.1 ({platform.system()}; {platform.release()})"
        }
        self.api_url = "https://metron.cloud/api/{}/"

    @sleep_and_retry
    @limits(calls=20, period=ONE_MINUTE)
    def call(self, endpoint, params=None):
        if params is None:
            params = {}

        url = self.api_url.format("/".join(str(e) for e in endpoint))
        response = requests.get(
            url, params=params, auth=(self.username, self.passwd), headers=self.header
        )
        data = response.json()

        if "detail" in data:
            raise exceptions.ApiError(data["detail"])

        return data

    def creator(self, _id):
        try:
            result = creator.CreatorSchema().load(self.call(["creator", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def creators_list(self, params=None):
        if params is None:
            params = {}
        return creators_list.CreatorsList(self.call(["creator"], params=params))

    def character(self, _id):
        try:
            result = character.CharacterSchema().load(self.call(["character", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def characters_list(self, params=None):
        if params is None:
            params = {}
        return characters_list.CharactersList(self.call(["character"], params=params))

    def publisher(self, _id):
        try:
            result = publisher.PublisherSchema().load(self.call(["publisher", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def publishers_list(self, params=None):
        if params is None:
            params = {}
        return publishers_list.PublishersList(self.call(["publisher"], params=params))

    def team(self, _id):
        try:
            result = team.TeamSchema().load(self.call(["team", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def teams_list(self, params=None):
        if params is None:
            params = {}
        return teams_list.TeamsList(self.call(["team"], params=params))

    def arc(self, _id):
        try:
            result = arc.ArcSchema().load(self.call(["arc", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def arcs_list(self, params=None):
        if params is None:
            params = {}
        return arcs_list.ArcsList(self.call(["arc"], params=params))

    def series(self, _id):
        try:
            result = series.SeriesSchema().load(self.call(["series", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def series_list(self, params=None):
        if params is None:
            params = {}
        return series_list.SeriesList(self.call(["series"], params=params))

    def issue(self, _id):
        try:
            result = issue.IssueSchema().load(self.call(["issue", _id]))
        except ValidationError as error:
            raise exceptions.ApiError(error)

        result.session = self
        return result

    def issues_list(self, params=None):
        if params is None:
            params = {}
        return issues_list.IssuesList(self.call(["issue"], params=params))

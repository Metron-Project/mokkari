"""
TeamsList module.

This module provides the following classes:

- TeamsList
"""
from marshmallow import ValidationError

from mokkari import exceptions, team


class TeamsList:
    """The TeamsList object contains a list of `Team` objects."""

    def __init__(self, response):
        """Initialize a new TeamsList."""
        self.teams = []

        schema = team.TeamSchema()
        for team_dict in response["results"]:
            try:
                result = schema.load(team_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error)

            self.teams.append(result)

    def __iter__(self):
        """Return an iterator object."""
        return iter(self.teams)

    def __len__(self):
        """Return the length of the object."""
        return len(self.teams)

    def __getitem__(self, index: int):
        """Return the object of a at index."""
        return self.teams[index]

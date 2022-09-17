"""
Team module.

This module provides the following classes:

- Team
- TeamSchema
- TeamsList
"""
from marshmallow import EXCLUDE, Schema, ValidationError, fields, post_load

from mokkari import creator, exceptions


class Team:
    """
    The Team object contains information for teams.

    Args:
        **kwargs (Any): The keyword arguments is used for setting team data from Metron.

    Attributes:
        id (int): The Metron identification number for the team.
        name (str): The name of the team.
        desc (str): The description of the team.
        image (url): The url for an image associated with the team.
        creators (list[:obj:`Creator`]): A list of creators for the team.
        modified (datetime): The date/time the team was last changed.
    """

    def __init__(self, **kwargs):
        """Initialize a new Team."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class TeamSchema(Schema):
    """
    Schema for the Team API.

    .. versionchanged:: 1.0.0

        - Added ``modified`` field

    .. versionchanged:: 2.0.2
        - Removed ``wikipedia`` field
    """

    id = fields.Int()
    name = fields.Str()
    desc = fields.Str()
    image = fields.Url(allow_none=True)
    creators = fields.Nested(creator.CreatorSchema, many=True)
    modified = fields.DateTime()

    class Meta:
        """Any unknown fields will be excluded."""

        unknown = EXCLUDE
        datetime = "%Y-%m-%dT%H:%M:%S%z"

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the Team object.

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            A :obj:`Team` object
        """
        return Team(**data)


class TeamsList:
    """
    The :obj:`TeamsList` object contains a list of teams.

    Attributes:
        id (int): The Metron identification number for the team.
        name (str): The name of the team.
        modified (datetime): The date/time the team was last changed.

    Returns:
        A list of teams.
    """

    def __init__(self, response):
        """Initialize a new TeamsList."""
        self.teams = []

        schema = TeamSchema()
        for team_dict in response["results"]:
            try:
                result = schema.load(team_dict)
            except ValidationError as error:
                raise exceptions.ApiError(error) from error

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

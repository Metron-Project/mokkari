"""
Team module.

This module provides the following classes:

- Team
- TeamSchema
"""
from marshmallow import INCLUDE, Schema, fields, post_load

from mokkari import creator


class Team:
    """
    The Team object contains information for teams.

    :param `**kwargs`: The keyword arguments is used for setting team data from Metron.
    """

    def __init__(self, **kwargs):
        """Intialize a new Team."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class TeamSchema(Schema):
    """Schema for the Team API."""

    id = fields.Int()
    name = fields.Str()
    desc = fields.Str()
    wikipedia = fields.Str()
    image = fields.Url()
    creators = fields.Nested(creator.CreatorSchema, many=True)

    class Meta:
        """Any unknown fields will be included."""

        unknown = INCLUDE

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the arc object.

        :param data: Data from Metron reponse.

        :returns: :class:`Team` object
        :rtype: Team
        """
        return Team(**data)

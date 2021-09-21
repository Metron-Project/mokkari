"""
Character module.

This module provides the following classes:

- Character
- CharacterSchema
"""
from marshmallow import INCLUDE, Schema, fields, post_load

from mokkari import creator, team


class Character:
    """
    The Character object contains information for characters.

    :param `**kwargs`: The keyword arguments is used for setting character data from Metron.
    """

    def __init__(self, **kwargs):
        """Intialize a new Character."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class CharacterSchema(Schema):
    """
    Schema for the Character API.

    .. versionchanged:: 1.0.0

        - Added ``modified`` field
    """

    id = fields.Int()
    name = fields.Str()
    alias = fields.List(fields.Str)
    desc = fields.Str()
    wikipedia = fields.Str()
    image = fields.Url()
    creators = fields.Nested(creator.CreatorSchema, many=True)
    teams = fields.Nested(team.TeamSchema, many=True)
    modified = fields.DateTime()

    class Meta:
        """Any unknown fields will be included."""

        unknown = INCLUDE
        datetime = "%Y-%m-%dT%H:%M:%S%z"

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the character object.

        :param data: Data from Metron response.

        :returns: :class:`Character` object
        :rtype: Character
        """
        return Character(**data)

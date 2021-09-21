"""
Creator module.

This module provides the following classes:

- Creator
- CreatorSchema
"""
from marshmallow import INCLUDE, Schema, fields, post_load


class Creator:
    """
    The Creator object contains information for creators.

    :param `**kwargs`: The keyword arguments is used for setting creator data from Metron.
    """

    def __init__(self, **kwargs):
        """Intialize a new Creator."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class CreatorSchema(Schema):
    """
    Schema for the Creator API.

    .. versionchanged:: 1.0.0

        - Added ``modified`` field
    """

    id = fields.Int()
    name = fields.Str()
    birth = fields.Date(allow_none=True)
    death = fields.Date(allow_none=True)
    desc = fields.Str()
    wikipedia = fields.Str()
    image = fields.Url()
    modified = fields.DateTime()

    class Meta:
        """Any unknown fields will be included."""

        unknown = INCLUDE
        dateformat = "%Y-%m-%d"
        datetime = "%Y-%m-%dT%H:%M:%S%z"

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the Creator object.

        :param data: Data from Metron response.

        :returns: :class:`Creator` object
        :rtype: Creator
        """
        return Creator(**data)

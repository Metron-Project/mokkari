"""
Publisher module.

This module provides the following classes:

- Publisher
- PublisherSchema
"""
from marshmallow import INCLUDE, Schema, fields, post_load


class Publisher:
    """
    The Publisher object contains information for publishers.

    :param `**kwargs`: The keyword arguments is used for setting publisher data from Metron.
    """

    def __init__(self, **kwargs):
        """Intialize a new Publisher."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class PublisherSchema(Schema):
    """
    Schema for the Publisher API.

    .. versionchanged:: 1.0.0

        - Added ``modified`` field
    """

    id = fields.Int()
    name = fields.Str()
    founded = fields.Int()
    desc = fields.Str()
    wikipedia = fields.Str()
    image = fields.Url()
    modified = fields.DateTime()

    class Meta:
        """Any unknown fields will be included."""

        unknown = INCLUDE
        datetime = "%Y-%m-%dT%H:%M:%S%z"

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the Publisher object.

        :param data: Data from Metron response.

        :returns: :class:`Publisher` object
        :rtype: Publisher
        """
        return Publisher(**data)

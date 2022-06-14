"""
Genre Module.

This module provides the following classes:

- Genre
- GenreSchema
"""
from marshmallow import EXCLUDE, Schema, fields, post_load


class Genre:
    """
    The Genre object contains information about a Series or Issue genre.

    :param `**kwargs`: The keyword arguments is used for setting genre data from Metron.
    """

    def __init__(self, **kwargs):
        """Initialize a new Genre."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class GenreSchema(Schema):
    """Schema for the Genre."""

    id = fields.Int()
    name = fields.Str()

    class Meta:
        """Any unknown fields will be excluded."""

        unknown = EXCLUDE

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the Genre object.

        :param data: Data from Metron response.

        :returns: :class:`Genre` object
        :rtype: Genre
        """
        return Genre(**data)

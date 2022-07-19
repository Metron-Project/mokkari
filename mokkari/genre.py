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

    Args:
        **kwargs (Any): The keyword arguments is used for setting genre data from Metron.

    Attributes:
        id (int): The Metron identification number for the genre.
        name (str): The name of the genre.
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

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            A :obj:`Genre` object.
        """
        return Genre(**data)

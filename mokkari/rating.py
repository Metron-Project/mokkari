"""
Rating module.

This module provides the following classes:

- Rating
- RatingSchema
"""
from marshmallow import EXCLUDE, Schema, fields, post_load


class Rating:
    """
    The rating object contains information for issue's rating.

    Args:
        **kwargs (Any): The keyword arguments is used for setting Rating data from Metron.

    Attributes:
        id (int): The Metron identification number for the rating.
        name (str): The name of the rating.
    """

    def __init__(self, **kwargs):
        """Initialize a Rating."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class RatingSchema(Schema):
    """Schema for Ratings."""

    id = fields.Int()
    name = fields.Str()

    class Meta:
        """Any unknown fields will be excluded."""

        unknown = EXCLUDE

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the rating object.

        Args:
            data (Any): Data from the Metron response
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            A :obj: `Rating` object.
        """
        return Rating(**data)

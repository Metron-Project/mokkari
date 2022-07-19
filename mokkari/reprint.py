"""
Reprint module.

This module provides the following classes:

- Reprint
- ReprintSchema
- ReprintsList
"""
from marshmallow import EXCLUDE, Schema, fields, post_load


class Reprint:
    """
    The Reprint object contains information for a reprint issue.

    Args:
        **kwargs (Any): The keyword arguments is used for setting reprint issue
        data from Metron.

    Attributes:
        id (int): The Metron identification number for the issue.
        issue (str): The name of the issue being reprinted.
    """

    def __init__(self, **kwargs):
        """Initialize a new Reprint."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class ReprintSchema(Schema):
    """Schema for the Reprint API."""

    id = fields.Int()
    issue = fields.Str()

    class Meta:
        """Any unknown fields will be excluded."""

        unknown = EXCLUDE

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the reprint object.

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            A :obj:`Reprint` object.
        """
        return Reprint(**data)

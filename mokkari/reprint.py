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

    :param `**kwargs`: The keyword arguments is used for setting reprint data from Metron.
    """

    def __init__(self, **kwargs):
        """Intialize a new Reprint."""
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

        :param data: Data from Metron response.

        :returns: :class:`Reprint` object
        :rtype: Reprint
        """
        return Reprint(**data)

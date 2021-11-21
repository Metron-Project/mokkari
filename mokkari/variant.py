"""
Variant module.

This module provides the following classes:

- Variant
- VariantSchema
"""
from marshmallow import EXCLUDE, Schema, fields, post_load


class Variant:
    """
    The Variant object contains information for variant issues.

    :param `**kwargs`: The keyword arguments is used for setting variant issue data.
    """

    def __init__(self, **kwargs):
        """Intialize a new Variant."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class VariantSchema(Schema):
    """Schema for the Variant API."""

    name = fields.Str()
    sku = fields.Str()
    image = fields.Url()

    class Meta:
        """Any unknown fields will be excluded."""

        unknown = EXCLUDE

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the Variant object.

        :param data: Data from Metron response.

        :returns: :class:`Variant` object
        :rtype: Variant
        """
        return Variant(**data)

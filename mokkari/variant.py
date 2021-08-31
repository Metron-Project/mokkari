"""
Variant module.

This module provides the following classes:

- Variant
- VariantSchema
"""
from marshmallow import INCLUDE, Schema, fields, post_load


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
        """Any unknown fields will be included."""

        unknown = INCLUDE

    @post_load
    def make_object(self, data, **kwargs):
        """
        Make the arc object.

        :param data: Data from Metron reponse.

        :returns: :class:`Variant` object
        :rtype: Variant
        """
        return Variant(**data)

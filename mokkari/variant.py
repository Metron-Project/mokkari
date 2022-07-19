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

    Args:
        **kwargs (Any): The keyword arguments is used for setting arc data from Metron.

    Attributes:
        name (int): The name of the variant cover.
        sku (str): The stock keeping unit for the variant cover.
        image (url): The url for an image for the variant cover.
    """

    def __init__(self, **kwargs):
        """Initialize a new Variant."""
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

        Args:
            data (Any): Data from Metron response.
            **kwargs (Any): Any additional keyword arguments.

        Returns:
            An :obj:`Variant` object
        """
        return Variant(**data)

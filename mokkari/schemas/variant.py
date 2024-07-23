"""Variant module.

This module provides the following classes:

- Variant
"""

from pydantic import HttpUrl

from mokkari.schemas import BaseModel


class Variant(BaseModel):
    """A data model representing a variant cover.

    Attributes:
        name (str): The name of the variant.
        sku (str): The stock keeping unit (SKU) of the variant.
        upc (str): The Universal Product Code (UPC) of the variant.
        image (HttpUrl): The image URL of the variant.
    """

    name: str
    sku: str
    upc: str
    image: HttpUrl

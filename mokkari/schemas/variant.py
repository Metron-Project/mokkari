"""
Variant module.

This module provides the following classes:

- Variant
"""

from pydantic import HttpUrl

from mokkari.schemas import BaseModel


class Variant(BaseModel):
    """
    The :obj:`Variant` object contains information about a variant cover..

    Attributes:
        name (str): The name of the variant cover.
        sku (str): The sku of the variant cover.
        upc (str): The upc of the variant cover.
        image (HttpUrl): The url for the variant cover.
    """

    name: str | None = None
    sku: str | None = None
    upc: str | None = None
    image: HttpUrl

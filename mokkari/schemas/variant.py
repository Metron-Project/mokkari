"""Variant module.

This module provides the following classes:

- Variant
"""

__all__ = ["Variant", "VariantPost", "VariantPostResponse"]

from decimal import Decimal

from pydantic import HttpUrl

from mokkari.schemas import BaseModel


class Variant(BaseModel):
    """A data model representing a variant cover.

    Attributes:
        name (str): The name of the variant.
        price (Decimal | None): The price of the variant.
        sku (str): The stock keeping unit (SKU) of the variant.
        upc (str): The Universal Product Code (UPC) of the variant.
        image (HttpUrl): The image URL of the variant.
    """

    name: str
    price: Decimal | None = None
    sku: str
    upc: str
    image: HttpUrl


class VariantPost(BaseModel):
    """A data model representing a variant cover to be posted.

    Attributes:
        issue (int): The issue number of the variant.
        image (str | None): The image URL of the variant. Defaults to None.
        name (str | None): The name of the variant. Defaults to None.
        price (Decimal | None): The price of the variant.
        sku (str | None): The stock keeping unit (SKU) of the variant. Defaults to None.
        upc (str | None): The Universal Product Code (UPC) of the variant. Defaults to None.
    """

    issue: int
    image: str | None = None
    name: str | None = None
    price: Decimal | None = None
    sku: str | None = None
    upc: str | None = None


class VariantPostResponse(VariantPost):
    """A data model representing the response after posting a variant cover.

    Attributes:
        id (int): The ID of the variant.
        issue (int): The issue number of the variant.
        image (str | None): The image URL of the variant. Defaults to None.
        name (str | None): The name of the variant. Defaults to None.
        price (Decimal | None): The price of the variant.
        price_currency (str | None): The price currency of the variant. Defaults to None
        sku (str | None): The stock keeping unit (SKU) of the variant. Defaults to None.
        upc (str | None): The Universal Product Code (UPC) of the variant. Defaults to None.
    """

    id: int
    price_currency: str

"""Creator module.

This module provides the following classes:

- Creator
"""

__all__ = ["Creator", "CreatorPost"]

from datetime import date

from pydantic import HttpUrl, PastDate

from mokkari.schemas import BaseModel
from mokkari.schemas.base import BaseResource


class Creator(BaseResource):
    """A data model representing a creator that extends BaseResource.

    Attributes:
        birth (PastDate, optional): The birthdate of the creator.
        death (date, optional): The death date of the creator.
        desc (str): The description of the creator.
        image (HttpUrl, optional): The image URL of the creator.
        alias (list[str], optional): The aliases of the creator.
        cv_id (int, optional): The Comic Vine ID of the creator.
        gcd_id (int, optional): The Grand Comics Database ID of the creator.
        resource_url (HttpUrl): The URL of the creator resource.
    """

    birth: PastDate | None = None
    death: date | None = None
    desc: str
    image: HttpUrl | None = None
    alias: list[str] | None = None
    cv_id: int | None = None
    gcd_id: int | None = None
    resource_url: HttpUrl


class CreatorPost(BaseModel):
    """A data model representing a creator to be created.

    Attributes:
        name (str, optional): The name of the creator.
        birth (PastDate, optional): The birthdate of the creator.
        death (date, optional): The death date of the creator.
        desc (str, optional): The description of the creator.
        image (str, optional): The image URL of the creator.
        alias (list[str], optional): The aliases of the creator.
        cv_id (int, optional): The Comic Vine ID of the creator.
        gcd_id (int, optional): The Grand Comics Database ID of the creator.
    """

    name: str | None = None
    birth: PastDate | None = None
    death: date | None = None
    desc: str | None = None
    image: str | None = None
    alias: list[str] | None = None
    cv_id: int | None = None
    gcd_id: int | None = None

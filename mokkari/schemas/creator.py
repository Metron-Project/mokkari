"""
Creator module.

This module provides the following classes:

- Creator
"""

from datetime import date

from pydantic import HttpUrl, PastDate

from mokkari.schemas.base import BaseResource


class Creator(BaseResource):
    """
    The Creator object extends :obj:`BaseResource` providing  all information for a creator.

    Attributes:
        birth (date): The date of birth for the creator.
        death (date): The date of death for the creator.
        desc (str): The description of the creator.
        image (HttpUrl): The url for an image associated with the creator.
        alias (list[str]): The alias of the creator.
        cv_id (int): Comic Vine ID for the creator.
        resource_url (HttpUrl): The url for the resource.
    """

    birth: PastDate | None = None
    death: date | None = None
    desc: str | None = None
    image: HttpUrl | None = None
    alias: list[str] | None = None
    cv_id: int | None = None
    resource_url: HttpUrl

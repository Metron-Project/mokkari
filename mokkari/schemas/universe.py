"""
Universe module.

This module provides the following classes:

- BaseUniverse
- Universe
"""

from datetime import datetime

from pydantic import HttpUrl

from mokkari.schemas import BaseModel
from mokkari.schemas.generic import GenericItem


class BaseUniverse(BaseModel):
    """
    The :obj:`BaseUniverse` object contains a list of universes.

    Attributes:
        id (int): The Metron identification number for the universe.
        name (str): The name of the universe.
        modified (datetime): The date/time the universe was last changed.

    Returns:
        A list of universes.
    """

    id: int
    name: str
    modified: datetime


class Universe(BaseUniverse):
    """
    The Universe object extends the :obj:`BaseUniverse` by containing all information for a universe.

    Attributes:
        publisher (int): The Metron identification number for the publisher
        designation (str): The designation of the universe.
        desc (str): The description of the universe.
        image (url): The url for an image associated with the universe.
        resource_url (url): The url for the resource.
    """
    publisher: GenericItem
    designation: str | None = None
    desc: str | None = None
    image: HttpUrl | None = None
    resource_url: HttpUrl

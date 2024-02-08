"""
Universe module.

This module provides the following classes:

- Universe
"""

from pydantic import HttpUrl

from mokkari.schemas.base import BaseResource
from mokkari.schemas.generic import GenericItem


class Universe(BaseResource):
    """
    The Universe object extends the :obj:`BaseResource` by containing information for a universe.

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

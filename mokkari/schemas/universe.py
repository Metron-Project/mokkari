"""Universe module.

This module provides the following classes:

- Universe
"""

from pydantic import HttpUrl

from mokkari.schemas.base import BaseResource
from mokkari.schemas.generic import GenericItem


class Universe(BaseResource):
    """A data model representing a universe that extends BaseResource.

    Attributes:
        publisher (GenericItem): The publisher of the universe.
        designation (str): The designation of the universe.
        desc (str): The description of the universe.
        image (HttpUrl, optional): The image URL of the universe.
        gcd_id (int, optional): The Grand Comics Database ID of the universe.
        resource_url (HttpUrl): The URL of the universe resource.
    """

    publisher: GenericItem
    designation: str
    desc: str
    image: HttpUrl | None = None
    gcd_id: int | None = None
    resource_url: HttpUrl

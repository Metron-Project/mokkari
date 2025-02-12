"""Universe module.

This module provides the following classes:

- Universe
- UniversePost
- UniversePostResponse
"""

__all__ = ["Universe", "UniversePost", "UniversePostResponse"]

from pydantic import HttpUrl

from mokkari.schemas import BaseModel
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


class UniversePost(BaseModel):
    """A data model representing a universe to be created.

    Attributes:
        publisher (int, optional): The ID of the publisher of the universe.
        name (str, optional): The name of the universe.
        designation (str, optional): The designation of the universe.
        desc (str, optional): The description of the universe.
        image (str, optional): The image URL of the universe.
        gcd_id (int, optional): The Grand Comics Database ID of the universe.
    """

    publisher: int | None = None
    name: str | None = None
    designation: str | None = None
    desc: str | None = None
    gcd_id: int | None = None
    image: str | None = None


class UniversePostResponse(BaseResource, UniversePost):
    """A data model representing the response from creating a universe.

    Attributes:
        publisher (int, optional): The ID of the publisher of the universe.
        name (str, optional): The name of the universe.
        designation (str, optional): The designation of the universe.
        desc (str, optional): The description of the universe.
        image (str, optional): The image URL of the universe.
        gcd_id (int, optional): The Grand Comics Database ID of the universe.
        resource_url (HttpUrl): The URL of the universe resource.
    """

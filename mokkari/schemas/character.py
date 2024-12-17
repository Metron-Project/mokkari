# ruff: noqa: RUF012
"""Character module.

This module provides the following classes:

- Character
"""

from pydantic import HttpUrl

from mokkari.schemas.base import BaseResource


class Character(BaseResource):
    """A data model representing a character that extends BaseResource.

    Attributes:
        alias (list[str], optional): The aliases of the character.
        desc (str): The description of the character.
        image (HttpUrl, optional): The image URL of the character.
        creators (list[BaseResource], optional): The creators of the character.
        teams (list[BaseResource], optional): The teams the character belongs to.
        universes (list[BaseResource], optional): The universes the character is associated with.
        cv_id (int, optional): The Comic Vine ID of the character.
        gcd_id (int, optional): The Grand Comics Database ID of the character.
        resource_url (HttpUrl): The URL of the character resource.
    """

    alias: list[str] | None = None
    desc: str
    image: HttpUrl | None = None
    creators: list[BaseResource] = []
    teams: list[BaseResource] = []
    universes: list[BaseResource] = []
    cv_id: int | None = None
    gcd_id: int | None = None
    resource_url: HttpUrl

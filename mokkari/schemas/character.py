# ruff: noqa: RUF012
"""
Character module.

This module provides the following classes:

- Character
"""

from pydantic import HttpUrl

from mokkari.schemas.base import BaseResource


class Character(BaseResource):
    """
    The Character object extends :obj:`BaseResource` providing  all information for a character.

    Attributes:
        alias (list[str]): The alias of the character.
        desc (str): The description of the character.
        image (url): The url for an image associated with the character.
        creators (list[:obj:`Generic`]): A list of creators for the character.
        teams (list[:obj:`Generic`]): A list of teams for the character.
        cv_id (int): Comic Vine ID for the character.
        resource_url (url): The url for the resource.
    """

    alias: list[str] | None = None
    desc: str | None = None
    image: HttpUrl | None = None
    creators: list[BaseResource] = []
    teams: list[BaseResource] = []
    universes: list[BaseResource] = []
    cv_id: int | None = None
    resource_url: HttpUrl

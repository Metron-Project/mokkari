"""
Character module.

This module provides the following classes:

- BaseCharacter
- Character
"""

from datetime import datetime

from pydantic import HttpUrl

from mokkari.schemas import BaseModel
from mokkari.schemas.creator import BaseCreator
from mokkari.schemas.team import BaseTeam
from mokkari.schemas.universe import BaseUniverse


class BaseCharacter(BaseModel):
    """
    The :obj:`BaseCharacter` object contains a list of characters.

    Attributes:
        id (int): The Metron identification number for the character.
        name (str): The name of the character.
        modified (datetime): The date/time the team was last changed.
    """

    id: int
    name: str
    modified: datetime


class Character(BaseCharacter):
    """
    The Character object extends :obj:`BaseCharacter` providing  all information for a character.

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
    creators: list[BaseCreator] = []
    teams: list[BaseTeam] = []
    universes: list[BaseUniverse] = []
    cv_id: int | None = None
    resource_url: HttpUrl

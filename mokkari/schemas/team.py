"""
Team module.

This module provides the following classes:

- BaseTeam
- Team
"""

from datetime import datetime

from pydantic import HttpUrl

from mokkari.schemas import BaseModel
from mokkari.schemas.creator import BaseCreator
from mokkari.schemas.universe import BaseUniverse


class BaseTeam(BaseModel):
    """
    The :obj:`BaseTeam` object contains a list of teams.

    Attributes:
        id (int): The Metron identification number for the team.
        name (str): The name of the team.
        modified (datetime): The date/time the team was last changed.

    Returns:
        A list of teams.
    """

    id: int
    name: str
    modified: datetime


class Team(BaseTeam):
    """
    The Team object extends the :obj:`BaseTeam` by containing all information for a team.

    Attributes:
        desc (str): The description of the team.
        image (url): The url for an image associated with the team.
        creators (list[:obj:`Generic`]): A list of creators for the team.
        cv_id (int): Comic Vine ID for the team.
        resource_url (url): The url for the resource.
    """

    desc: str | None = None
    image: HttpUrl | None = None
    creators: list[BaseCreator] = []
    universes: list[BaseUniverse] = []
    cv_id: int | None = None
    resource_url: HttpUrl

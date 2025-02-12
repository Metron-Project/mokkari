# ruff: noqa: RUF012
"""Team module.

This module provides the following classes:

- Team
- TeamPost
- TeamPostResponse
"""

__all__ = ["Team", "TeamPost", "TeamPostResponse"]
from pydantic import HttpUrl

from mokkari.schemas import BaseModel
from mokkari.schemas.base import BaseResource


class Team(BaseResource):
    """A data model representing a team that extends BaseResource.

    Attributes:
        desc (str): The description of the team.
        image (HttpUrl, optional): The image URL of the team.
        creators (list[BaseResource], optional): The creators of the team.
        universes (list[BaseResource], optional): The universes the team is associated with.
        cv_id (int, optional): The Comic Vine ID of the team.
        gcd_id (int, optional): The Grand Comics Database ID of the team.
        resource_url (HttpUrl): The URL of the team resource.
    """

    desc: str
    image: HttpUrl | None = None
    creators: list[BaseResource] = []
    universes: list[BaseResource] = []
    cv_id: int | None = None
    gcd_id: int | None = None
    resource_url: HttpUrl


class TeamPost(BaseModel):
    """A data model representing a team to be created.

    Attributes:
        name (str, optional): The name of the team.
        desc (str, optional): The description of the team.
        image (str, optional): The image URL of the team.
        creators (list[int], optional): The IDs of the creators of the team.
        universes (list[int], optional): The IDs of the universes the team is associated with.
        cv_id (int, optional): The Comic Vine ID of the team.
        gcd_id (int, optional): The Grand Comics Database ID of the team.
    """

    name: str | None = None
    desc: str | None = None
    image: str | None = None
    creators: list[int] | None = None
    universes: list[int] | None = None
    cv_id: int | None = None
    gcd_id: int | None = None


class TeamPostResponse(BaseResource, TeamPost):
    """A data model representing the response from creating a team.

    Attributes:
        id: (int) The ID of the team.
        name (str): The name of the team.
        desc (str, optional): The description of the team.
        image (str, optional): The image URL of the team.
        creators (list[int], optional): The IDs of the creators of the team.
        universes (list[int], optional): The IDs of the universes the team is associated with.
        cv_id (int, optional): The Comic Vine ID of the team.
        gcd_id (int, optional): The Grand Comics Database ID of the team.
        resource_url (HttpUrl): The URL of the team resource.
    """

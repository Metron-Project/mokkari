# ruff: noqa: RUF012
"""Team module.

This module provides the following classes:

- Team
"""

from pydantic import HttpUrl

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

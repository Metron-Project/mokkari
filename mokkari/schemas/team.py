# ruff: noqa: RUF012
"""
Team module.

This module provides the following classes:

- Team
"""

from pydantic import HttpUrl

from mokkari.schemas.base import BaseResource


class Team(BaseResource):
    """
    The Team object extends the :obj:`BaseResource` by containing all information for a team.

    Attributes:
        desc (str): The description of the team.
        image (url): The url for an image associated with the team.
        creators (list[:obj:`Generic`]): A list of creators for the team.
        cv_id (int): Comic Vine ID for the team.
        resource_url (url): The url for the resource.
    """

    desc: str | None = None
    image: HttpUrl | None = None
    creators: list[BaseResource] = []
    universes: list[BaseResource] = []
    cv_id: int | None = None
    resource_url: HttpUrl

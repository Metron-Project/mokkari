"""User module.

This module provides the following classes:

- User
"""

__all__ = ["User"]

from mokkari.schemas import BaseModel


class User(BaseModel):
    """A data model representing a user.

    Attributes:
        id (int): The unique identifier of the user.
        username (str): The username of the user (150 characters or fewer).
    """

    id: int
    username: str

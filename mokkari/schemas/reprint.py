"""Reprint module.

This module provides the following classes:

- Reprint
"""

from mokkari.schemas import BaseModel


class Reprint(BaseModel):
    """A data model representing a reprint.

    Attributes:
        id (int): The unique identifier of the reprint.
        issue (str): The issue being reprinted.
    """

    id: int
    issue: str

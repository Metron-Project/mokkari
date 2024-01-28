"""
Reprint module.

This module provides the following classes:

- Reprint
"""

from mokkari.schemas import BaseModel


class Reprint(BaseModel):
    """
    The :obj:`Reprint` object contains a list of reprinted issues.

    Attributes:
        id (int): The Metron identification number for the team.
        issue (str): The name of the issue.
    """

    id: int
    issue: str

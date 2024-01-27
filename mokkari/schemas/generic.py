"""
Generic module.

This module provides the following classes:

- Generic
"""

from mokkari.schemas import BaseModel


class Generic(BaseModel):
    id: int
    name: str

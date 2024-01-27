"""
Arc module.

This module provides the following classes:

- Arc
- BaseArc
"""
from datetime import datetime

from pydantic import HttpUrl
from mokkari.schemas import BaseModel


class BaseArc(BaseModel):
    id: int
    name: str
    modified: datetime


class Arc(BaseArc):
    desc: str | None = None
    image: HttpUrl | None = None
    cv_id: int | None = None
    resource_url: HttpUrl

"""
Creator module.

This module provides the following classes:

- BaseCreator
- Creator
"""
from datetime import date, datetime

from pydantic import PastDate, HttpUrl

from mokkari.schemas import BaseModel


class BaseCreator(BaseModel):
    id: int
    name: str
    modified: datetime


class Creator(BaseCreator):
    birth: PastDate | None = None
    death: date | None = None
    desc: str | None = None
    image: HttpUrl | None = None
    alias: list[str] | None = None
    cv_id: int | None = None
    resource_url: HttpUrl

from datetime import datetime

from pydantic import HttpUrl
from mokkari.schemas import BaseModel


class BasePublisher(BaseModel):
    id: int
    name: str
    modified: datetime


class Publisher(BasePublisher):
    founded: int | None = None
    desc: str | None = None
    image: HttpUrl | None = None
    cv_id: int | None = None
    resource_url: HttpUrl

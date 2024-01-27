from pydantic import HttpUrl

from mokkari.schemas import BaseModel


class Variant(BaseModel):
    name: str | None = None
    sku: str | None = None
    image: HttpUrl

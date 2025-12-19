"""Collection module.

This module provides the following classes:

- BookFormat
- GradingCompany
- Grade
- Rating
- CollectionIssue
- CollectionList
- CollectionRead
- MissingIssue
- MissingSeries
- CollectionFormatStat
- CollectionStats
"""

__all__ = [
    "BookFormat",
    "CollectionFormatStat",
    "CollectionIssue",
    "CollectionList",
    "CollectionRead",
    "CollectionStats",
    "Grade",
    "GradingCompany",
    "MissingIssue",
    "MissingSeries",
    "Rating",
]

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import Field

from mokkari.schemas import BaseModel
from mokkari.schemas.issue import BasicSeries
from mokkari.schemas.user import User


class BookFormat(str, Enum):
    """Enumeration of book formats.

    Values:

        PRINT: Physical printed comic book
        DIGITAL: Digital/electronic comic book
        BOTH: Both print and digital formats
    """

    PRINT = "PRINT"
    DIGITAL = "DIGITAL"
    BOTH = "BOTH"


class GradingCompany(str, Enum):
    """Enumeration of professional grading companies.

    Values:

        CGC: CGC (Certified Guaranty Company)
        CBCS: CBCS (Comic Book Certification Service)
        PGX: PGX (Professional Grading Experts)
    """

    CGC = "CGC"
    CBCS = "CBCS"
    PGX = "PGX"


class Grade(float, Enum):
    """Enumeration of comic book grades using the CGC scale.

    Values:

        GEM_MINT: 10.0 (Gem Mint)
        MINT: 9.9 (Mint)
        NM_M: 9.8 (NM/M - Near Mint/Mint)
        NM_PLUS: 9.6 (NM+ - Near Mint+)
        NM: 9.4 (NM - Near Mint)
        NM_MINUS: 9.2 (NM- - Near Mint-)
        VF_NM: 9.0 (VF/NM - Very Fine/Near Mint)
        VF_PLUS: 8.5 (VF+ - Very Fine+)
        VF: 8.0 (VF - Very Fine)
        VF_MINUS: 7.5 (VF- - Very Fine-)
        FN_VF: 7.0 (FN/VF - Fine/Very Fine)
        FN_PLUS: 6.5 (FN+ - Fine+)
        FN: 6.0 (FN - Fine)
        FN_MINUS: 5.5 (FN- - Fine-)
        VG_FN: 5.0 (VG/FN - Very Good/Fine)
        VG_PLUS: 4.5 (VG+ - Very Good+)
        VG: 4.0 (VG - Very Good)
        VG_MINUS: 3.5 (VG- - Very Good-)
        GD_VG: 3.0 (GD/VG - Good/Very Good)
        GD_PLUS: 2.5 (GD+ - Good+)
        GD: 2.0 (GD - Good)
        GD_MINUS: 1.8 (GD- - Good-)
        FR_GD: 1.5 (FR/GD - Fair/Good)
        FR: 1.0 (FR - Fair)
        PR: 0.5 (PR - Poor)
    """

    GEM_MINT = 10.0
    MINT = 9.9
    NM_M = 9.8
    NM_PLUS = 9.6
    NM = 9.4
    NM_MINUS = 9.2
    VF_NM = 9.0
    VF_PLUS = 8.5
    VF = 8.0
    VF_MINUS = 7.5
    FN_VF = 7.0
    FN_PLUS = 6.5
    FN = 6.0
    FN_MINUS = 5.5
    VG_FN = 5.0
    VG_PLUS = 4.5
    VG = 4.0
    VG_MINUS = 3.5
    GD_VG = 3.0
    GD_PLUS = 2.5
    GD = 2.0
    GD_MINUS = 1.8
    FR_GD = 1.5
    FR = 1.0
    PR = 0.5


class Rating(int, Enum):
    """Enumeration of star ratings (1-5) for issues.

    Values:

        ONE: 1 star
        TWO: 2 stars
        THREE: 3 stars
        FOUR: 4 stars
        FIVE: 5 stars
    """

    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5


class CollectionIssue(BaseModel):
    """A data model representing an issue in a collection (without image and cover_hash).

    Attributes:
        id (int): The unique identifier of the issue.
        series (BasicSeries): The series associated with the issue.
        number (str): The number of the issue.
        cover_date (date): The cover date of the issue.
        store_date (date, optional): The store date of the issue.
        modified (datetime): The date and time when the issue was last modified.
    """

    id: int
    series: BasicSeries
    number: str
    cover_date: date
    store_date: date | None = None
    modified: datetime


class CollectionList(BaseModel):
    """A data model representing a collection item in list view.

    Attributes:
        id (int): The unique identifier of the collection item.
        user (User): The user who owns this collection item.
        issue (CollectionIssue): The issue associated with this collection item.
        quantity (int): Number of copies owned.
        book_format (str): Format of the comic (print, digital, or both).
        grade (float, optional): Comic book grade (CGC scale).
        grading_company (str): Professional grading company.
        purchase_date (date, optional): Date when the issue was purchased.
        is_read (bool): Whether the issue has been read.
        rating (int, optional): Star rating (1-5) for this issue.
        modified (datetime): The date and time when the collection item was last modified.
    """

    id: int
    user: User
    issue: CollectionIssue
    quantity: int = Field(ge=0, le=32767)
    book_format: str
    grade: float | None = None
    grading_company: str
    purchase_date: date | None = None
    is_read: bool
    rating: int | None = None
    modified: datetime


class CollectionRead(BaseModel):
    """A data model representing a collection item in detailed view.

    Attributes:
        id (int): The unique identifier of the collection item.
        user (User): The user who owns this collection item.
        issue (CollectionIssue): The issue associated with this collection item.
        quantity (int): Number of copies owned.
        book_format (str): Format of the comic (print, digital, or both).
        grade (float, optional): Comic book grade (CGC scale).
        grading_company (str): Professional grading company.
        purchase_date (date, optional): Date when the issue was purchased.
        purchase_price (Decimal, optional): Price paid for this issue.
        purchase_store (str): Store or vendor where purchased.
        storage_location (str): Physical location where the issue is stored.
        notes (str): Additional notes about this collection item.
        is_read (bool): Whether the issue has been read.
        date_read (date, optional): Date when the issue was read.
        rating (int, optional): Star rating (1-5) for this issue.
        resource_url (str): URL of the collection item resource.
        created_on (datetime): The date and time when the collection item was created.
        modified (datetime): The date and time when the collection item was last modified.
    """

    id: int
    user: User
    issue: CollectionIssue
    quantity: int = Field(ge=0, le=32767)
    book_format: str
    grade: float | None = None
    grading_company: str
    purchase_date: date | None = None
    purchase_price: Decimal | None = None
    purchase_store: str = ""
    storage_location: str = ""
    notes: str = ""
    is_read: bool
    date_read: date | None = None
    rating: int | None = None
    resource_url: str
    created_on: datetime
    modified: datetime


class MissingIssue(BaseModel):
    """A data model representing a missing issue in a series.

    Attributes:
        id (int): The unique identifier of the issue.
        series (BasicSeries): The series associated with the issue.
        number (str): The number of the issue.
        cover_date (date): The cover date of the issue.
        store_date (date, optional): The store date of the issue.
    """

    id: int
    series: BasicSeries
    number: str
    cover_date: date
    store_date: date | None = None


class MissingSeries(BaseModel):
    """A data model representing a series with missing issues.

    Attributes:
        id (int): The unique identifier of the series.
        name (str): The name of the series.
        sort_name (str): The sort name of the series.
        year_began (int): The year the series began.
        year_end (int, optional): The year the series ended.
    """

    id: int
    name: str
    sort_name: str
    year_began: int
    year_end: int | None = None


class CollectionFormatStat(BaseModel):
    """A data model representing statistics for a specific book format.

    Attributes:
        book_format (str): Format of the comic (print, digital, or both).
        count (int): Number of items in this format.
    """

    book_format: str
    count: int


class CollectionStats(BaseModel):
    """A data model representing statistics about a user's collection.

    Attributes:
        total_items (int): Total number of collection items.
        total_quantity (int): Total quantity of all items.
        total_value (str): Total value of the collection.
        read_count (int): Number of items that have been read.
        unread_count (int): Number of items that have not been read.
        by_format (list[CollectionFormatStat]): Statistics broken down by book format.
    """

    total_items: int
    total_quantity: int
    total_value: str
    read_count: int
    unread_count: int
    by_format: list[CollectionFormatStat] = Field(default_factory=list)

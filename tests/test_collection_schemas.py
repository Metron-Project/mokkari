"""Tests for the collection module."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from mokkari.schemas.collection import (
    BookFormat,
    CollectionFormatStat,
    CollectionIssue,
    CollectionList,
    CollectionRead,
    CollectionStats,
    Grade,
    GradingCompany,
    MissingIssue,
    MissingSeries,
    Rating,
    User,
)


# Test fixtures
@pytest.fixture
def user_data():
    """Sample user data."""
    return {"id": 1, "username": "testuser"}


@pytest.fixture
def basic_series_data():
    """Sample basic series data."""
    return {"name": "Batman", "volume": 1, "year_began": 1940}


@pytest.fixture
def collection_issue_data(basic_series_data):
    """Sample collection issue data."""
    return {
        "id": 1,
        "series": basic_series_data,
        "number": "1",
        "cover_date": "2024-01-01",
        "store_date": "2023-12-15",
        "modified": "2024-01-01T12:00:00Z",
    }


@pytest.fixture
def collection_list_data(user_data, collection_issue_data):
    """Sample collection list data."""
    return {
        "id": 1,
        "user": user_data,
        "issue": collection_issue_data,
        "quantity": 1,
        "book_format": "PRINT",
        "grade": 9.8,
        "grading_company": "CGC",
        "purchase_date": "2024-01-15",
        "is_read": True,
        "rating": 5,
        "modified": "2024-01-01T12:00:00Z",
    }


@pytest.fixture
def collection_read_data(user_data, collection_issue_data):
    """Sample collection read data."""
    return {
        "id": 1,
        "user": user_data,
        "issue": collection_issue_data,
        "quantity": 1,
        "book_format": "PRINT",
        "grade": 9.8,
        "grading_company": "CGC",
        "purchase_date": "2024-01-15",
        "purchase_price": "49.99",
        "purchase_store": "Local Comic Shop",
        "storage_location": "Box 1",
        "notes": "First appearance",
        "is_read": True,
        "date_read": "2024-01-20",
        "rating": 5,
        "resource_url": "https://metron.cloud/api/collection/1/",
        "created_on": "2024-01-01T10:00:00Z",
        "modified": "2024-01-01T12:00:00Z",
    }


# User tests
def test_user_valid_data(user_data):
    """Test User model with valid data."""
    user = User(**user_data)
    assert user.id == 1
    assert user.username == "testuser"


def test_user_missing_required_field():
    """Test User model with missing required field."""
    with pytest.raises(ValidationError):
        User(id=1)


# BookFormat enum tests
def test_book_format_enum():
    """Test BookFormat enum values."""
    assert BookFormat.PRINT.value == "PRINT"
    assert BookFormat.DIGITAL.value == "DIGITAL"
    assert BookFormat.BOTH.value == "BOTH"


# GradingCompany enum tests
def test_grading_company_enum():
    """Test GradingCompany enum values."""
    assert GradingCompany.CGC.value == "CGC"
    assert GradingCompany.CBCS.value == "CBCS"
    assert GradingCompany.PGX.value == "PGX"


# Grade enum tests
def test_grade_enum():
    """Test Grade enum values."""
    assert Grade.GEM_MINT.value == 10.0
    assert Grade.NM_M.value == 9.8
    assert Grade.PR.value == 0.5


# Rating enum tests
def test_rating_enum():
    """Test Rating enum values."""
    assert Rating.ONE.value == 1
    assert Rating.FIVE.value == 5


# CollectionIssue tests
def test_collection_issue_valid_data(collection_issue_data):
    """Test CollectionIssue model with valid data."""
    issue = CollectionIssue(**collection_issue_data)
    assert issue.id == 1
    assert issue.series.name == "Batman"
    assert issue.number == "1"
    assert issue.cover_date == date(2024, 1, 1)
    assert issue.store_date == date(2023, 12, 15)


def test_collection_issue_optional_store_date(basic_series_data):
    """Test CollectionIssue with optional store_date."""
    data = {
        "id": 1,
        "series": basic_series_data,
        "number": "1",
        "cover_date": "2024-01-01",
        "modified": "2024-01-01T12:00:00Z",
    }
    issue = CollectionIssue(**data)
    assert issue.store_date is None


# CollectionList tests
def test_collection_list_valid_data(collection_list_data):
    """Test CollectionList model with valid data."""
    collection = CollectionList(**collection_list_data)
    assert collection.id == 1
    assert collection.user.username == "testuser"
    assert collection.issue.number == "1"
    assert collection.quantity == 1
    assert collection.book_format == "PRINT"
    assert collection.grade == 9.8
    assert collection.is_read is True
    assert collection.rating == 5


def test_collection_list_optional_fields(user_data, collection_issue_data):
    """Test CollectionList with optional fields."""
    data = {
        "id": 1,
        "user": user_data,
        "issue": collection_issue_data,
        "quantity": 1,
        "book_format": "PRINT",
        "grading_company": "",
        "is_read": False,
        "modified": "2024-01-01T12:00:00Z",
    }
    collection = CollectionList(**data)
    assert collection.grade is None
    assert collection.purchase_date is None
    assert collection.rating is None


# CollectionRead tests
def test_collection_read_valid_data(collection_read_data):
    """Test CollectionRead model with valid data."""
    collection = CollectionRead(**collection_read_data)
    assert collection.id == 1
    assert collection.user.username == "testuser"
    assert collection.issue.number == "1"
    assert collection.quantity == 1
    assert collection.book_format == "PRINT"
    assert collection.grade == 9.8
    assert collection.grading_company == "CGC"
    assert collection.purchase_price == Decimal("49.99")
    assert collection.purchase_store == "Local Comic Shop"
    assert collection.storage_location == "Box 1"
    assert collection.notes == "First appearance"
    assert collection.is_read is True
    assert collection.date_read == date(2024, 1, 20)
    assert collection.rating == 5


def test_collection_read_empty_strings(user_data, collection_issue_data):
    """Test CollectionRead with empty string defaults."""
    data = {
        "id": 1,
        "user": user_data,
        "issue": collection_issue_data,
        "quantity": 1,
        "book_format": "PRINT",
        "grading_company": "",
        "is_read": False,
        "resource_url": "https://metron.cloud/api/collection/1/",
        "created_on": "2024-01-01T10:00:00Z",
        "modified": "2024-01-01T12:00:00Z",
    }
    collection = CollectionRead(**data)
    assert collection.purchase_store == ""
    assert collection.storage_location == ""
    assert collection.notes == ""


# MissingIssue tests
def test_missing_issue_valid_data(basic_series_data):
    """Test MissingIssue model with valid data."""
    data = {
        "id": 1,
        "series": basic_series_data,
        "number": "2",
        "cover_date": "2024-02-01",
        "store_date": "2024-01-15",
    }
    missing = MissingIssue(**data)
    assert missing.id == 1
    assert missing.series.name == "Batman"
    assert missing.number == "2"
    assert missing.cover_date == date(2024, 2, 1)


# MissingSeries tests
def test_missing_series_valid_data():
    """Test MissingSeries model with valid data."""
    data = {
        "id": 1,
        "name": "Batman",
        "sort_name": "Batman",
        "year_began": 1940,
        "year_end": 2011,
    }
    series = MissingSeries(**data)
    assert series.id == 1
    assert series.name == "Batman"
    assert series.year_began == 1940
    assert series.year_end == 2011


def test_missing_series_no_end_year():
    """Test MissingSeries with no end year."""
    data = {
        "id": 1,
        "name": "Batman",
        "sort_name": "Batman",
        "year_began": 2011,
    }
    series = MissingSeries(**data)
    assert series.year_end is None


# CollectionFormatStat tests
def test_collection_format_stat_valid_data():
    """Test CollectionFormatStat model with valid data."""
    data = {"book_format": "PRINT", "count": 150}
    stat = CollectionFormatStat(**data)
    assert stat.book_format == "PRINT"
    assert stat.count == 150


# CollectionStats tests
def test_collection_stats_valid_data():
    """Test CollectionStats model with valid data."""
    data = {
        "total_items": 200,
        "total_quantity": 250,
        "total_value": "5000.00",
        "read_count": 150,
        "unread_count": 50,
        "by_format": [
            {"book_format": "PRINT", "count": 180},
            {"book_format": "DIGITAL", "count": 20},
        ],
    }
    stats = CollectionStats(**data)
    assert stats.total_items == 200
    assert stats.total_quantity == 250
    assert stats.total_value == "5000.00"
    assert stats.read_count == 150
    assert stats.unread_count == 50
    assert len(stats.by_format) == 2
    assert stats.by_format[0].book_format == "PRINT"


def test_collection_stats_empty_format_list():
    """Test CollectionStats with empty format list."""
    data = {
        "total_items": 0,
        "total_quantity": 0,
        "total_value": "0.00",
        "read_count": 0,
        "unread_count": 0,
    }
    stats = CollectionStats(**data)
    assert stats.by_format == []

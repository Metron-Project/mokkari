"""Tests for the reading list module."""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from mokkari.schemas.reading_list import (
    AttributionSource,
    ReadingListIssue,
    ReadingListItem,
    ReadingListList,
    ReadingListRead,
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
def reading_list_issue_data(basic_series_data):
    """Sample reading list issue data."""
    return {
        "id": 1,
        "series": basic_series_data,
        "number": "1",
        "cover_date": "2023-01-01",
        "store_date": "2022-12-15",
        "cv_id": 123456,
        "gcd_id": 654321,
        "modified": "2023-01-01T12:00:00Z",
    }


@pytest.fixture
def reading_list_item_data(reading_list_issue_data):
    """Sample reading list item data."""
    return {"id": 1, "issue": reading_list_issue_data, "order": 1, "issue_type": "issue"}


@pytest.fixture
def reading_list_list_data(user_data):
    """Sample reading list list data."""
    return {
        "id": 1,
        "name": "My Reading List",
        "slug": "my-reading-list",
        "user": user_data,
        "is_private": False,
        "attribution_source": "CBRO",
        "average_rating": 4.5,
        "rating_count": 10,
        "modified": "2023-01-01T12:00:00Z",
    }


@pytest.fixture
def reading_list_read_data(user_data):
    """Sample reading list read data."""
    return {
        "id": 1,
        "user": user_data,
        "name": "My Reading List",
        "slug": "my-reading-list",
        "desc": "A test reading list",
        "is_private": False,
        "attribution_source": "CBRO",
        "attribution_url": "https://example.com/reading-list",
        "average_rating": 4.5,
        "rating_count": 10,
        "items_url": "https://api.example.com/reading_list/1/items/",
        "resource_url": "https://api.example.com/reading_list/1/",
        "modified": "2023-01-01T12:00:00Z",
    }


# User model tests
def test_user_creation(user_data):
    """Test creating a User with required data."""
    user = User(**user_data)
    assert user.id == 1
    assert user.username == "testuser"


def test_user_validation_missing_required_fields():
    """Test User validation with missing required fields."""
    with pytest.raises(ValidationError) as exc_info:
        User(id=1)  # Missing username
    assert "username" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        User(username="testuser")  # Missing id
    assert "id" in str(exc_info.value)


# AttributionSource enum tests
def test_attribution_source_enum():
    """Test AttributionSource enum values."""
    assert AttributionSource.CBRO == "CBRO"
    assert AttributionSource.CMRO == "CMRO"
    assert AttributionSource.CBH == "CBH"
    assert AttributionSource.CBT == "CBT"
    assert AttributionSource.MG == "MG"
    assert AttributionSource.HTLC == "HTLC"
    assert AttributionSource.LOCG == "LOCG"
    assert AttributionSource.OTHER == "OTHER"


# ReadingListIssue model tests
def test_reading_list_issue_creation(reading_list_issue_data):
    """Test creating a ReadingListIssue with all fields."""
    issue = ReadingListIssue(**reading_list_issue_data)
    assert issue.id == 1
    assert issue.series.name == "Batman"
    assert issue.number == "1"
    assert isinstance(issue.cover_date, date)
    assert isinstance(issue.store_date, date)
    assert issue.cv_id == 123456
    assert issue.gcd_id == 654321
    assert isinstance(issue.modified, datetime)


def test_reading_list_issue_creation_minimal(basic_series_data):
    """Test creating a ReadingListIssue with minimal required data."""
    data = {
        "id": 1,
        "series": basic_series_data,
        "number": "1",
        "cover_date": "2023-01-01",
        "modified": "2023-01-01T12:00:00Z",
    }
    issue = ReadingListIssue(**data)
    assert issue.id == 1
    assert issue.store_date is None
    assert issue.cv_id is None
    assert issue.gcd_id is None


def test_reading_list_issue_validation_missing_fields(basic_series_data):
    """Test ReadingListIssue validation with missing required fields."""
    with pytest.raises(ValidationError):
        ReadingListIssue(
            id=1,
            series=basic_series_data,
            number="1",
            modified="2023-01-01T12:00:00Z",
        )  # Missing cover_date


# ReadingListItem model tests
def test_reading_list_item_creation(reading_list_item_data):
    """Test creating a ReadingListItem with all fields."""
    item = ReadingListItem(**reading_list_item_data)
    assert item.id == 1
    assert isinstance(item.issue, ReadingListIssue)
    assert item.issue.number == "1"
    assert item.order == 1


def test_reading_list_item_creation_minimal(reading_list_issue_data):
    """Test creating a ReadingListItem with minimal required data."""
    data = {"id": 1, "issue": reading_list_issue_data, "issue_type": "issue"}
    item = ReadingListItem(**data)
    assert item.id == 1
    assert item.order is None


def test_reading_list_item_validation_missing_issue():
    """Test ReadingListItem validation with missing issue."""
    with pytest.raises(ValidationError) as exc_info:
        ReadingListItem(id=1, issue_type="issue")  # Missing issue
    assert "issue" in str(exc_info.value)


def test_reading_list_item_validation_missing_issue_type(reading_list_issue_data):
    """Test ReadingListItem validation with missing issue_type."""
    with pytest.raises(ValidationError) as exc_info:
        ReadingListItem(id=1, issue=reading_list_issue_data)  # Missing issue_type
    assert "issue_type" in str(exc_info.value)


def test_reading_list_item_empty_issue_type(reading_list_issue_data):
    """Test ReadingListItem accepts empty string for issue_type.

    The API may return an empty string for issue_type, so we verify
    that it's accepted by the model.
    """
    data = {"id": 1, "issue": reading_list_issue_data, "issue_type": ""}
    item = ReadingListItem(**data)
    assert item.id == 1
    assert item.issue_type == ""


def test_reading_list_item_various_issue_types(reading_list_issue_data):
    """Test ReadingListItem with various issue_type values."""
    issue_types = ["issue", "annual", "hardcover", "trade paperback", "digital"]
    for issue_type in issue_types:
        data = {"id": 1, "issue": reading_list_issue_data, "issue_type": issue_type}
        item = ReadingListItem(**data)
        assert item.issue_type == issue_type


# ReadingListList model tests
def test_reading_list_list_creation(reading_list_list_data):
    """Test creating a ReadingListList with all fields."""
    reading_list = ReadingListList(**reading_list_list_data)
    assert reading_list.id == 1
    assert reading_list.name == "My Reading List"
    assert reading_list.slug == "my-reading-list"
    assert isinstance(reading_list.user, User)
    assert reading_list.user.username == "testuser"
    assert reading_list.is_private is False
    assert reading_list.attribution_source == AttributionSource.CBRO
    assert isinstance(reading_list.modified, datetime)


def test_reading_list_list_creation_minimal(user_data):
    """Test creating a ReadingListList with minimal required data."""
    data = {
        "id": 1,
        "name": "My Reading List",
        "slug": "my-reading-list",
        "user": user_data,
        "average_rating": 0.0,
        "rating_count": 0,
        "modified": "2023-01-01T12:00:00Z",
    }
    reading_list = ReadingListList(**data)
    assert reading_list.id == 1
    assert reading_list.is_private is False
    assert reading_list.attribution_source is None


def test_reading_list_list_validation_missing_fields():
    """Test ReadingListList validation with missing required fields."""
    with pytest.raises(ValidationError) as exc_info:
        ReadingListList(id=1, name="Test")  # Missing slug, user, modified
    error_str = str(exc_info.value)
    assert "slug" in error_str
    assert "user" in error_str
    assert "modified" in error_str


# ReadingListRead model tests
def test_reading_list_read_creation(reading_list_read_data):
    """Test creating a ReadingListRead with all fields."""
    reading_list = ReadingListRead(**reading_list_read_data)
    assert reading_list.id == 1
    assert isinstance(reading_list.user, User)
    assert reading_list.name == "My Reading List"
    assert reading_list.slug == "my-reading-list"
    assert reading_list.desc == "A test reading list"
    assert reading_list.is_private is False
    assert reading_list.attribution_source == "CBRO"
    assert str(reading_list.attribution_url) == "https://example.com/reading-list"
    assert reading_list.items_url == "https://api.example.com/reading_list/1/items/"
    assert reading_list.resource_url == "https://api.example.com/reading_list/1/"
    assert isinstance(reading_list.modified, datetime)


def test_reading_list_read_creation_minimal(user_data):
    """Test creating a ReadingListRead with minimal required data."""
    data = {
        "id": 1,
        "user": user_data,
        "name": "My Reading List",
        "slug": "my-reading-list",
        "attribution_source": "CBRO",
        "average_rating": 0.0,
        "rating_count": 0,
        "items_url": "https://api.example.com/reading_list/1/items/",
        "resource_url": "https://api.example.com/reading_list/1/",
        "modified": "2023-01-01T12:00:00Z",
    }
    reading_list = ReadingListRead(**data)
    assert reading_list.id == 1
    assert reading_list.desc == ""
    assert reading_list.is_private is False
    assert reading_list.attribution_url is None


def test_reading_list_read_validation_missing_fields():
    """Test ReadingListRead validation with missing required fields."""
    with pytest.raises(ValidationError) as exc_info:
        ReadingListRead(id=1, name="Test")  # Missing multiple required fields
    error_str = str(exc_info.value)
    assert "user" in error_str
    assert "slug" in error_str
    assert "attribution_source" in error_str
    assert "items_url" in error_str
    assert "resource_url" in error_str
    assert "modified" in error_str


def test_reading_list_read_invalid_url():
    """Test ReadingListRead validation with invalid attribution URL."""
    data = {
        "id": 1,
        "user": {"id": 1, "username": "testuser"},
        "name": "My Reading List",
        "slug": "my-reading-list",
        "attribution_source": "CBRO",
        "attribution_url": "not_a_valid_url",
        "average_rating": 0.0,
        "rating_count": 0,
        "items_url": "https://api.example.com/reading_list/1/items/",
        "resource_url": "https://api.example.com/reading_list/1/",
        "modified": "2023-01-01T12:00:00Z",
    }
    with pytest.raises(ValidationError):
        ReadingListRead(**data)


def test_reading_list_read_empty_attribution_source(user_data):
    """Test ReadingListRead accepts empty string for attribution_source.

    Since attribution_source is a plain str field (not an enum) in ReadingListRead,
    empty strings should be valid.
    """
    data = {
        "id": 175,
        "user": user_data,
        "name": "Star Wars: Crimson Reign",
        "slug": "star-wars-crimson-reign",
        "attribution_source": "",
        "average_rating": 0.0,
        "rating_count": 0,
        "items_url": "https://api.example.com/reading_list/175/items/",
        "resource_url": "https://api.example.com/reading_list/175/",
        "modified": "2025-12-13T00:44:51.789220-05:00",
    }
    reading_list = ReadingListRead(**data)
    assert reading_list.id == 175
    assert reading_list.attribution_source == ""


def test_reading_list_no_average_rating(user_data):
    """Test ReadingListRead accepts None for average rating.

    If there are no ratings the average rating is None.
    """
    data = {
        "id": 175,
        "user": user_data,
        "name": "Star Wars: Crimson Reign",
        "slug": "star-wars-crimson-reign",
        "attribution_source": "",
        "average_rating": None,
        "rating_count": 0,
        "items_url": "https://api.example.com/reading_list/175/items/",
        "resource_url": "https://api.example.com/reading_list/175/",
        "modified": "2025-12-13T00:44:51.789220-05:00",
    }
    reading_list = ReadingListRead(**data)
    assert reading_list.id == 175
    assert reading_list.average_rating is None


# Edge cases and integration tests
def test_private_reading_list(user_data):
    """Test creating a private reading list."""
    data = {
        "id": 1,
        "name": "My Private List",
        "slug": "my-private-list",
        "user": user_data,
        "is_private": True,
        "average_rating": 0.0,
        "rating_count": 0,
        "modified": "2023-01-01T12:00:00Z",
    }
    reading_list = ReadingListList(**data)
    assert reading_list.is_private is True


def test_reading_list_with_different_attribution_sources(user_data):
    """Test creating reading lists with different attribution sources."""
    sources = ["CBRO", "CMRO", "CBH", "CBT", "MG", "HTLC", "LOCG", "OTHER"]
    for source in sources:
        data = {
            "id": 1,
            "name": "Test List",
            "slug": "test-list",
            "user": user_data,
            "attribution_source": source,
            "average_rating": 0.0,
            "rating_count": 0,
            "modified": "2023-01-01T12:00:00Z",
        }
        reading_list = ReadingListList(**data)
        assert reading_list.attribution_source.value == source


def test_reading_list_list_empty_attribution_source(user_data):
    """Test that empty string attribution_source is converted to None.

    This handles the case where the API returns an empty string instead of null
    for the attribution_source field.
    """
    data = {
        "id": 175,
        "name": "Star Wars: Crimson Reign",
        "slug": "star-wars-crimson-reign",
        "user": user_data,
        "is_private": False,
        "attribution_source": "",
        "average_rating": 0.0,
        "rating_count": 0,
        "modified": "2025-12-13T00:44:51.789220-05:00",
    }
    reading_list = ReadingListList(**data)
    assert reading_list.id == 175
    assert reading_list.name == "Star Wars: Crimson Reign"
    assert reading_list.attribution_source is None


def test_reading_list_list_invalid_attribution_source(user_data):
    """Test that invalid attribution sources raise ValidationError."""
    data = {
        "id": 1,
        "name": "Test List",
        "slug": "test-list",
        "user": user_data,
        "attribution_source": "INVALID",
        "average_rating": 0.0,
        "rating_count": 0,
        "modified": "2023-01-01T12:00:00Z",
    }
    with pytest.raises(ValidationError) as exc_info:
        ReadingListList(**data)
    assert "attribution_source" in str(exc_info.value)


def test_reading_list_list_no_average_rating(user_data):
    """Test ReadingListList accepts None for average rating.

    If there are no ratings the average rating is None.
    """
    data = {
        "id": 175,
        "name": "Star Wars: Crimson Reign",
        "slug": "star-wars-crimson-reign",
        "user": user_data,
        "is_private": False,
        "attribution_source": "",
        "average_rating": None,
        "rating_count": 0,
        "modified": "2025-12-13T00:44:51.789220-05:00",
    }
    reading_list = ReadingListList(**data)
    assert reading_list.id == 175
    assert reading_list.average_rating is None

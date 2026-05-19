"""Tests for the wish_list module."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from mokkari.schemas.wish_list import (
    AcquireWishListItem,
    Currency,
    Priority,
    WishList,
    WishListAddItem,
    WishListItemList,
    WishListItemRead,
)


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


# Priority enum tests
def test_priority_enum_values():
    """Test Priority enum values."""
    assert Priority.ONE.value == 1
    assert Priority.TWO.value == 2
    assert Priority.THREE.value == 3
    assert Priority.FOUR.value == 4
    assert Priority.FIVE.value == 5


# Currency enum tests
def test_currency_enum_values():
    """Test Currency enum values."""
    assert Currency.USD.value == "USD"
    assert Currency.GBP.value == "GBP"


# WishList tests
def test_wish_list_valid_data():
    """Test WishList model with valid data."""
    data = {
        "id": 1,
        "item_count": 5,
        "items_url": "https://metron.cloud/api/wish_list/1/items/",
        "modified": "2024-01-01T12:00:00Z",
    }
    wl = WishList(**data)
    assert wl.id == 1
    assert wl.item_count == 5
    assert wl.items_url == "https://metron.cloud/api/wish_list/1/items/"
    assert wl.modified.year == 2024


def test_wish_list_missing_required_field():
    """Test WishList model with missing required field."""
    with pytest.raises(ValidationError):
        WishList(id=1, item_count=5, modified="2024-01-01T12:00:00Z")  # type: ignore


# WishListItemList tests
def test_wish_list_item_list_valid_data(collection_issue_data):
    """Test WishListItemList model with valid data."""
    data = {
        "id": 10,
        "issue": collection_issue_data,
        "status": "Wanted",
        "priority": 3,
        "desired_grade": 9.8,
        "modified": "2024-01-01T12:00:00Z",
    }
    item = WishListItemList(**data)
    assert item.id == 10
    assert item.issue.number == "1"
    assert item.status == "Wanted"
    assert item.priority == Priority.THREE
    assert item.desired_grade == 9.8
    assert item.modified.year == 2024


def test_wish_list_item_list_optional_fields(collection_issue_data):
    """Test WishListItemList with optional fields omitted."""
    data = {
        "id": 10,
        "issue": collection_issue_data,
        "status": "Wanted",
        "modified": "2024-01-01T12:00:00Z",
    }
    item = WishListItemList(**data)
    assert item.priority is None
    assert item.desired_grade is None


def test_wish_list_item_list_missing_required_field(collection_issue_data):
    """Test WishListItemList with missing required field."""
    with pytest.raises(ValidationError):
        WishListItemList(id=10, issue=collection_issue_data)  # type: ignore


# WishListItemRead tests
def test_wish_list_item_read_valid_data(collection_issue_data):
    """Test WishListItemRead model with valid data."""
    data = {
        "id": 10,
        "issue": collection_issue_data,
        "status": "Wanted",
        "priority": 2,
        "desired_grade": 9.4,
        "max_price": "25.00",
        "max_price_currency": "USD",
        "notes": "Looking for high grade copy",
        "added_on": "2024-01-01T10:00:00Z",
        "modified": "2024-01-01T12:00:00Z",
    }
    item = WishListItemRead(**data)
    assert item.id == 10
    assert item.issue.series.name == "Batman"
    assert item.status == "Wanted"
    assert item.priority == Priority.TWO
    assert item.desired_grade == 9.4
    assert item.max_price == Decimal("25.00")
    assert item.max_price_currency == "USD"
    assert item.notes == "Looking for high grade copy"
    assert item.added_on.year == 2024
    assert item.modified.year == 2024


def test_wish_list_item_read_optional_fields(collection_issue_data):
    """Test WishListItemRead with optional fields omitted."""
    data = {
        "id": 10,
        "issue": collection_issue_data,
        "status": "Wanted",
        "added_on": "2024-01-01T10:00:00Z",
        "modified": "2024-01-01T12:00:00Z",
    }
    item = WishListItemRead(**data)
    assert item.priority is None
    assert item.desired_grade is None
    assert item.max_price is None
    assert item.max_price_currency is None
    assert item.notes == ""


# WishListAddItem tests
def test_wish_list_add_item_valid_data():
    """Test WishListAddItem model with valid data."""
    data = {
        "issue_id": 42,
        "priority": 1,
        "desired_grade": "9.8",
        "max_price": "50.00",
        "max_price_currency": "GBP",
        "notes": "Must have",
    }
    item = WishListAddItem(**data)
    assert item.issue_id == 42
    assert item.priority == 1
    assert item.desired_grade == Decimal("9.8")
    assert item.max_price == Decimal("50.00")
    assert item.max_price_currency == "GBP"
    assert item.notes == "Must have"


def test_wish_list_add_item_defaults():
    """Test WishListAddItem default values."""
    item = WishListAddItem(issue_id=1)
    assert item.priority == 3
    assert item.desired_grade is None
    assert item.max_price is None
    assert item.max_price_currency == "USD"
    assert item.notes == ""


def test_wish_list_add_item_missing_required_field():
    """Test WishListAddItem with missing required field."""
    with pytest.raises(ValidationError):
        WishListAddItem()  # type: ignore


def test_wish_list_add_item_priority_too_low():
    """Test WishListAddItem with priority below minimum."""
    with pytest.raises(ValidationError):
        WishListAddItem(issue_id=1, priority=0)


def test_wish_list_add_item_priority_too_high():
    """Test WishListAddItem with priority above maximum."""
    with pytest.raises(ValidationError):
        WishListAddItem(issue_id=1, priority=6)


# AcquireWishListItem tests
def test_acquire_wish_list_item_valid_data():
    """Test AcquireWishListItem model with valid data."""
    data = {
        "purchase_date": "2024-03-15",
        "purchase_price": "12.99",
        "purchase_price_currency": "USD",
        "purchase_store": "Local Comic Shop",
        "notes": "Good condition",
    }
    item = AcquireWishListItem(**data)
    assert item.purchase_date == date(2024, 3, 15)
    assert item.purchase_price == Decimal("12.99")
    assert item.purchase_price_currency == "USD"
    assert item.purchase_store == "Local Comic Shop"
    assert item.notes == "Good condition"


def test_acquire_wish_list_item_defaults():
    """Test AcquireWishListItem default values."""
    item = AcquireWishListItem()
    assert item.purchase_date is None
    assert item.purchase_price is None
    assert item.purchase_price_currency == "USD"
    assert item.purchase_store == ""
    assert item.notes == ""


def test_acquire_wish_list_item_gbp_currency():
    """Test AcquireWishListItem with GBP currency."""
    item = AcquireWishListItem(purchase_price="8.50", purchase_price_currency="GBP")
    assert item.purchase_price == Decimal("8.50")
    assert item.purchase_price_currency == "GBP"

"""Tests for the issue module without using classes."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from mokkari.schemas.issue import (
    BaseIssue,
    BasicSeries,
    CommonIssue,
    Credit,
    CreditPost,
    CreditPostResponse,
    Issue,
    IssuePost,
    IssuePostResponse,
    IssueSeries,
)


# Test fixtures
@pytest.fixture
def generic_item_data():
    """Sample generic item data."""
    return {"id": 1, "name": "Test Item"}


@pytest.fixture
def basic_series_data():
    """Sample basic series data."""
    return {"name": "Batman", "volume": 1, "year_began": 1940}


@pytest.fixture
def issue_series_data():
    """Sample issue series data."""
    return {
        "id": 1,
        "name": "Batman",
        "sort_name": "Batman",
        "volume": 1,
        "year_began": 1940,
        "series_type": {"id": 1, "name": "Ongoing Series"},
        "genres": [{"id": 1, "name": "Superhero"}],
    }


@pytest.fixture
def common_issue_data():
    """Sample common issue data."""
    return {
        "id": 1,
        "number": "1",
        "cover_date": "2023-01-01",
        "store_date": "2022-12-15",
        "foc_date": "2022-11-15",
        "image": "https://example.com/image.jpg",
        "cover_hash": "abc123",
        "modified": "2023-01-01T12:00:00Z",
    }


@pytest.fixture
def issue_post_data():
    """Sample issue post data."""
    return {
        "series": 1,
        "number": "1",
        "alt_number": "1A",
        "title": "Test Collection",
        "name": ["Story One", "Story Two"],
        "cover_date": "2023-01-01",
        "store_date": "2022-12-15",
        "foc_date": "2022-11-15",
        "price": "3.99",
        "rating": 1,
        "sku": "JUL230001",
        "isbn": "9781234567890",
        "upc": "123456789012",
        "page": 32,
        "desc": "A test issue description",
        "image": "https://example.com/image.jpg",
        "arcs": [1, 2, 3],
        "characters": [4, 5, 6],
        "teams": [7, 8],
        "universes": [9],
        "reprints": [10, 11],
        "cv_id": 123456,
        "gcd_id": 654321,
    }


# Credit model tests
def test_credit_creation_with_minimal_data():
    """Test creating a Credit with minimal required data."""
    data = {"id": 1, "creator": "Stan Lee"}
    credit = Credit(**data)
    assert credit.id == 1
    assert credit.creator == "Stan Lee"
    assert credit.role == []


def test_credit_creation_with_roles():
    """Test creating a Credit with roles."""
    data = {
        "id": 1,
        "creator": "Stan Lee",
        "role": [{"id": 1, "name": "Writer"}, {"id": 2, "name": "Editor"}],
    }
    credit = Credit(**data)
    assert len(credit.role) == 2
    assert credit.role[0].name == "Writer"
    assert credit.role[1].name == "Editor"


def test_credit_validation_missing_required_fields():
    """Test Credit validation with missing required fields."""
    with pytest.raises(ValidationError) as exc_info:
        Credit(id=1)  # Missing creator
    assert "creator" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        Credit(creator="Stan Lee")  # Missing id
    assert "id" in str(exc_info.value)


# CreditPost model tests
def test_credit_post_creation():
    """Test creating a CreditPost."""
    data = {"issue": 1, "creator": 2, "role": [1, 2, 3]}
    credit_post = CreditPost(**data)
    assert credit_post.issue == 1
    assert credit_post.creator == 2
    assert credit_post.role == [1, 2, 3]


def test_credit_post_validation_invalid_types():
    """Test CreditPost validation with invalid types."""
    with pytest.raises(ValidationError):
        CreditPost(issue="not_an_int", creator=2, role=[1])

    with pytest.raises(ValidationError):
        CreditPost(issue=1, creator="not_an_int", role=[1])

    with pytest.raises(ValidationError):
        CreditPost(issue=1, creator=2, role=["not_an_int"])


# CreditPostResponse model tests
def test_credit_post_response_creation():
    """Test creating a CreditPostResponse."""
    data = {"id": 123, "issue": 1, "creator": 2, "role": [1, 2], "modified": "2023-01-01T12:00:00Z"}
    response = CreditPostResponse(**data)
    assert response.id == 123
    assert response.issue == 1
    assert response.creator == 2
    assert response.role == [1, 2]
    assert isinstance(response.modified, datetime)


# BasicSeries model tests
def test_basic_series_creation(basic_series_data):
    """Test creating a BasicSeries."""
    series = BasicSeries(**basic_series_data)
    assert series.name == "Batman"
    assert series.volume == 1
    assert series.year_began == 1940


def test_basic_series_validation_missing_fields():
    """Test BasicSeries validation with missing required fields."""
    with pytest.raises(ValidationError):
        BasicSeries(name="Batman", volume=1)  # Missing year_began

    with pytest.raises(ValidationError):
        BasicSeries(volume=1, year_began=1940)  # Missing name

    with pytest.raises(ValidationError):
        BasicSeries(name="Batman", year_began=1940)  # Missing volume


def test_basic_series_validation_invalid_types():
    """Test BasicSeries validation with invalid types."""
    with pytest.raises(ValidationError):
        BasicSeries(name=123, volume=1, year_began=1940)

    with pytest.raises(ValidationError):
        BasicSeries(name="Batman", volume="not_int", year_began=1940)

    with pytest.raises(ValidationError):
        BasicSeries(name="Batman", volume=1, year_began="not_int")


# IssueSeries model tests
def test_issue_series_creation(issue_series_data):
    """Test creating an IssueSeries."""
    series = IssueSeries(**issue_series_data)
    assert series.id == 1
    assert series.name == "Batman"
    assert series.sort_name == "Batman"
    assert series.volume == 1
    assert series.year_began == 1940
    assert series.series_type.name == "Ongoing Series"
    assert len(series.genres) == 1
    assert series.genres[0].name == "Superhero"


def test_issue_series_creation_without_genres():
    """Test creating an IssueSeries without genres."""
    data = {
        "id": 1,
        "name": "Batman",
        "sort_name": "Batman",
        "volume": 1,
        "year_began": 1940,
        "series_type": {"id": 1, "name": "Ongoing Series"},
    }
    series = IssueSeries(**data)
    assert series.genres == []


def test_issue_series_validation_missing_series_type():
    """Test IssueSeries validation with missing series_type."""
    data = {"id": 1, "name": "Batman", "sort_name": "Batman", "volume": 1, "year_began": 1940}
    with pytest.raises(ValidationError) as exc_info:
        IssueSeries(**data)
    assert "series_type" in str(exc_info.value)


# CommonIssue model tests
def test_common_issue_creation(common_issue_data):
    """Test creating a CommonIssue."""
    issue = CommonIssue(**common_issue_data)
    assert issue.id == 1
    assert issue.number == "1"
    assert isinstance(issue.cover_date, date)
    assert isinstance(issue.store_date, date)
    assert isinstance(issue.foc_date, date)
    assert str(issue.image) == "https://example.com/image.jpg"
    assert issue.cover_hash == "abc123"
    assert isinstance(issue.modified, datetime)


def test_common_issue_creation_minimal_data():
    """Test creating a CommonIssue with minimal required data."""
    data = {"id": 1, "number": "1", "cover_date": "2023-01-01", "modified": "2023-01-01T12:00:00Z"}
    issue = CommonIssue(**data)
    assert issue.id == 1
    assert issue.number == "1"
    assert issue.store_date is None
    assert issue.foc_date is None
    assert issue.image is None
    assert issue.cover_hash == ""


def test_common_issue_validation_invalid_dates():
    """Test CommonIssue validation with invalid dates."""
    data = {
        "id": 1,
        "number": "1",
        "cover_date": "invalid_date",
        "modified": "2023-01-01T12:00:00Z",
    }
    with pytest.raises(ValidationError):
        CommonIssue(**data)


def test_common_issue_validation_invalid_url():
    """Test CommonIssue validation with invalid image URL."""
    data = {
        "id": 1,
        "number": "1",
        "cover_date": "2023-01-01",
        "image": "not_a_valid_url",
        "modified": "2023-01-01T12:00:00Z",
    }
    with pytest.raises(ValidationError):
        CommonIssue(**data)


# BaseIssue model tests
def test_base_issue_creation(common_issue_data, basic_series_data):
    """Test creating a BaseIssue."""
    data = {**common_issue_data, "issue": "Detective Comics #27", "series": basic_series_data}
    issue = BaseIssue(**data)
    assert issue.issue_name == "Detective Comics #27"
    assert issue.series.name == "Batman"
    assert isinstance(issue.series, BasicSeries)


def test_base_issue_field_alias():
    """Test BaseIssue field alias for issue_name."""
    data = {
        "id": 1,
        "number": "1",
        "cover_date": "2023-01-01",
        "modified": "2023-01-01T12:00:00Z",
        "issue": "Test Issue Name",
        "series": {"name": "Test Series", "volume": 1, "year_began": 2020},
    }
    issue = BaseIssue(**data)
    assert issue.issue_name == "Test Issue Name"


# Issue model tests
def test_issue_creation_full_data():
    """Test creating a full Issue with all fields."""
    now = datetime.now(tz=timezone.utc)
    data = {
        "id": 1,
        "number": "1",
        "cover_date": "2023-01-01",
        "store_date": "2022-12-15",
        "foc_date": "2022-11-15",
        "image": "https://example.com/image.jpg",
        "cover_hash": "abc123",
        "modified": "2023-01-01T12:00:00Z",
        "publisher": {"id": 1, "name": "DC Comics"},
        "imprint": {"id": 1, "name": "Vertigo"},
        "series": {
            "id": 1,
            "name": "Batman",
            "sort_name": "Batman",
            "volume": 1,
            "year_began": 1940,
            "series_type": {"id": 1, "name": "Ongoing Series"},
            "genres": [{"id": 1, "name": "Superhero"}],
        },
        "alt_number": "1A",
        "title": "The Dark Knight Returns",
        "name": ["Story One", "Story Two"],
        "price": "3.99",
        "price_currency": "USD",
        "rating": {"id": 1, "name": "T+"},
        "sku": "JUL230001",
        "isbn": "978-1234567890",
        "upc": "123456789012",
        "page": 32,
        "desc": "A great comic book issue.",
        "arcs": [{"id": 1, "name": "Year One", "modified": now}],
        "credits": [{"id": 1, "creator": "Frank Miller", "role": []}],
        "characters": [{"id": 1, "name": "Batman", "modified": now}],
        "teams": [{"id": 1, "name": "Justice League", "modified": now}],
        "universes": [{"id": 1, "name": "DC Universe", "modified": now}],
        "reprints": [],
        "variants": [],
        "cv_id": 123456,
        "gcd_id": 654321,
        "resource_url": "https://example.com/issue/1",
    }
    issue = Issue(**data)
    assert issue.id == 1
    assert issue.publisher.name == "DC Comics"
    assert issue.imprint.name == "Vertigo"
    assert issue.series.name == "Batman"
    assert issue.alt_number == "1A"
    assert issue.collection_title == "The Dark Knight Returns"
    assert issue.story_titles == ["Story One", "Story Two"]
    assert issue.price == Decimal("3.99")
    assert issue.rating.name == "T+"
    assert issue.page_count == 32
    assert issue.cv_id == 123456
    assert issue.gcd_id == 654321


def test_issue_creation_minimal_data():
    """Test creating an Issue with minimal required data."""
    data = {
        "id": 1,
        "number": "1",
        "cover_date": "2023-01-01",
        "modified": "2023-01-01T12:00:00Z",
        "publisher": {"id": 1, "name": "DC Comics"},
        "series": {
            "id": 1,
            "name": "Batman",
            "sort_name": "Batman",
            "volume": 1,
            "year_began": 1940,
            "series_type": {"id": 1, "name": "Ongoing Series"},
        },
        "alt_number": "",
        "title": "",
        "name": [],
        "rating": {"id": 1, "name": "T"},
        "sku": "",
        "isbn": "",
        "upc": "",
        "desc": "",
        "price": None,
        "price_currency": "",
        "resource_url": "https://example.com/issue/1",
    }
    issue = Issue(**data)
    assert issue.imprint is None
    assert issue.price is None
    assert issue.page_count is None
    assert issue.arcs == []
    assert issue.credits == []
    assert issue.characters == []
    assert issue.teams == []
    assert issue.universes == []
    assert issue.reprints == []
    assert issue.variants == []
    assert issue.cv_id is None
    assert issue.gcd_id is None


def test_issue_field_aliases():
    """Test Issue field aliases."""
    data = {
        "id": 1,
        "number": "1",
        "cover_date": "2023-01-01",
        "modified": "2023-01-01T12:00:00Z",
        "publisher": {"id": 1, "name": "DC Comics"},
        "series": {
            "id": 1,
            "name": "Batman",
            "sort_name": "Batman",
            "volume": 1,
            "year_began": 1940,
            "series_type": {"id": 1, "name": "Ongoing Series"},
        },
        "alt_number": "",
        "title": "Collection Title",
        "name": ["Story Title"],
        "rating": {"id": 1, "name": "T"},
        "sku": "",
        "isbn": "",
        "upc": "",
        "page": 24,
        "desc": "",
        "price": None,
        "price_currency": "",
        "resource_url": "https://example.com/issue/1",
    }
    issue = Issue(**data)
    assert issue.collection_title == "Collection Title"
    assert issue.story_titles == ["Story Title"]
    assert issue.page_count == 24


# IssuePost model tests
def test_issue_post_creation_full_data(issue_post_data):
    """Test creating an IssuePost with all fields."""
    issue_post = IssuePost(**issue_post_data)
    assert issue_post.series == 1
    assert issue_post.number == "1"
    assert issue_post.alt_number == "1A"
    assert issue_post.title == "Test Collection"
    assert issue_post.name == ["Story One", "Story Two"]
    assert isinstance(issue_post.price, Decimal)
    assert issue_post.rating == 1
    assert issue_post.page == 32
    assert issue_post.arcs == [1, 2, 3]


# IssuePost bad sku
def test_issue_post_bad_sku(issue_post_data):
    """Test creating an IssuePost with a bad sku."""
    data = issue_post_data
    data["sku"] = "123456789012345"  # 15 characters long
    with pytest.raises(ValidationError):
        IssuePost(**data)


# IssuePost bad isbn
def test_issue_post_bad_isbn(issue_post_data):
    """Test creating an IssuePost with a bad isbn."""
    data = issue_post_data
    data["isbn"] = "123456789012345"  # 15 characters long
    with pytest.raises(ValidationError):
        IssuePost(**data)


# IssuePost bad isbn
def test_issue_post_bad_upc(issue_post_data):
    """Test creating an IssuePost with a bad upc."""
    data = issue_post_data
    data["upc"] = "1234567890123456789012"  # 22 characters long
    with pytest.raises(ValidationError):
        IssuePost(**data)


def test_issue_post_creation_empty():
    """Test creating an empty IssuePost."""
    issue_post = IssuePost()
    assert issue_post.series is None
    assert issue_post.number is None
    assert issue_post.alt_number is None
    assert issue_post.title is None
    assert issue_post.name is None
    assert issue_post.cover_date is None
    assert issue_post.store_date is None
    assert issue_post.foc_date is None
    assert issue_post.price is None
    assert issue_post.rating is None
    assert issue_post.sku is None
    assert issue_post.isbn is None
    assert issue_post.upc is None
    assert issue_post.page is None
    assert issue_post.desc is None
    assert issue_post.image is None
    assert issue_post.arcs is None
    assert issue_post.characters is None
    assert issue_post.teams is None
    assert issue_post.universes is None
    assert issue_post.reprints is None
    assert issue_post.cv_id is None
    assert issue_post.gcd_id is None


def test_issue_post_validation_invalid_types():
    """Test IssuePost validation with invalid types."""
    with pytest.raises(ValidationError):
        IssuePost(series="not_an_int")

    with pytest.raises(ValidationError):
        IssuePost(rating="not_an_int")

    with pytest.raises(ValidationError):
        IssuePost(page="not_an_int")

    with pytest.raises(ValidationError):
        IssuePost(cover_date="invalid_date")


# IssuePostResponse model tests
def test_issue_post_response_creation():
    """Test creating an IssuePostResponse."""
    data = {
        "id": 123,
        "series": 1,
        "number": "1",
        "title": "Test Collection",
        "resource_url": "https://example.com/issue/123",
    }
    response = IssuePostResponse(**data)
    assert response.id == 123
    assert response.series == 1
    assert response.number == "1"
    assert response.title == "Test Collection"
    assert str(response.resource_url) == "https://example.com/issue/123"


def test_issue_post_response_validation_missing_required():
    """Test IssuePostResponse validation with missing required fields."""
    with pytest.raises(ValidationError) as exc_info:
        IssuePostResponse(series=1, number="1")  # Missing id and resource_url
    error_str = str(exc_info.value)
    assert "id" in error_str
    assert "resource_url" in error_str


# Edge cases and integration tests
def test_decimal_price_precision():
    """Test that price field handles decimal precision correctly."""
    issue_post = IssuePost(price="3.99")
    assert issue_post.price == Decimal("3.99")

    issue_post = IssuePost(price="10.999")
    assert issue_post.price == Decimal("10.999")


def test_empty_string_handling():
    """Test handling of empty strings in various fields."""
    data = {
        "id": 1,
        "number": "",
        "cover_date": "2023-01-01",
        "modified": "2023-01-01T12:00:00Z",
        "publisher": {"id": 1, "name": "DC Comics"},
        "series": {
            "id": 1,
            "name": "Batman",
            "sort_name": "Batman",
            "volume": 1,
            "year_began": 1940,
            "series_type": {"id": 1, "name": "Ongoing Series"},
        },
        "alt_number": "",
        "title": "",
        "name": [],
        "rating": {"id": 1, "name": "T"},
        "sku": "",
        "isbn": "",
        "upc": "",
        "desc": "",
        "price": None,
        "price_currency": "",
        "resource_url": "https://example.com/issue/1",
    }
    issue = Issue(**data)
    assert issue.number == ""
    assert issue.alt_number == ""
    assert issue.collection_title == ""
    assert issue.sku == ""
    assert issue.isbn == ""
    assert issue.upc == ""
    assert issue.desc == ""


def test_list_field_types():
    """Test that list fields accept the correct types."""
    # Test story_titles (list of strings)
    data = {
        "id": 1,
        "number": "1",
        "cover_date": "2023-01-01",
        "modified": "2023-01-01T12:00:00Z",
        "publisher": {"id": 1, "name": "DC Comics"},
        "series": {
            "id": 1,
            "name": "Batman",
            "sort_name": "Batman",
            "volume": 1,
            "year_began": 1940,
            "series_type": {"id": 1, "name": "Ongoing Series"},
        },
        "alt_number": "",
        "title": "",
        "name": ["Story 1", "Story 2", "Story 3"],
        "rating": {"id": 1, "name": "T"},
        "sku": "",
        "isbn": "",
        "upc": "",
        "desc": "",
        "price": None,
        "price_currency": "",
        "resource_url": "https://example.com/issue/1",
    }
    issue = Issue(**data)
    assert len(issue.story_titles) == 3
    assert all(isinstance(title, str) for title in issue.story_titles)


def test_optional_nested_objects():
    """Test handling of optional nested objects."""
    data = {
        "id": 1,
        "number": "1",
        "cover_date": "2023-01-01",
        "modified": "2023-01-01T12:00:00Z",
        "publisher": {"id": 1, "name": "DC Comics"},
        "imprint": None,  # Optional field set to None
        "series": {
            "id": 1,
            "name": "Batman",
            "sort_name": "Batman",
            "volume": 1,
            "year_began": 1940,
            "series_type": {"id": 1, "name": "Ongoing Series"},
        },
        "alt_number": "",
        "title": "",
        "name": [],
        "rating": {"id": 1, "name": "T"},
        "sku": "",
        "isbn": "",
        "upc": "",
        "desc": "",
        "price": None,
        "price_currency": "",
        "resource_url": "https://example.com/issue/1",
    }
    issue = Issue(**data)
    assert issue.imprint is None
    assert issue.publisher is not None

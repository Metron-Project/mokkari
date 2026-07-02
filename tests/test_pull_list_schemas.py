"""Tests for the pull_list module."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from mokkari.schemas.pull_list import (
    PullListIssue,
    PullListRead,
    PullListSeries,
    PullListSeriesDetail,
)


@pytest.fixture
def basic_series_data():
    """Sample basic series data (IssueListSeries)."""
    return {"id": 1, "name": "Batman", "volume": 1, "year_began": 1940}


# PullListRead tests
def test_pull_list_read_valid_data():
    """Test PullListRead model with valid data."""
    data = {
        "id": 1,
        "series_count": 5,
        "series_url": "https://metron.cloud/api/pull_list/1/series/",
        "modified": "2024-01-01T12:00:00Z",
    }
    pl = PullListRead(**data)
    assert pl.id == 1
    assert pl.series_count == 5
    assert pl.series_url == "https://metron.cloud/api/pull_list/1/series/"
    assert pl.modified.year == 2024


def test_pull_list_read_missing_required_field():
    """Test PullListRead model with missing required field."""
    with pytest.raises(ValidationError):
        PullListRead(id=1, series_count=5, modified="2024-01-01T12:00:00Z")  # type: ignore


# PullListIssue tests
def test_pull_list_issue_valid_data(basic_series_data):
    """Test PullListIssue model with valid data."""
    data = {
        "id": 100,
        "series": basic_series_data,
        "number": "1",
        "issue": "Batman #1",
        "cover_date": "2024-01-01",
        "store_date": "2023-12-27",
        "image": "https://metron.cloud/media/issue/batman-1.jpg",
        "modified": "2024-01-01T12:00:00Z",
    }
    issue = PullListIssue(**data)
    assert issue.id == 100
    assert issue.series.id == 1
    assert issue.series.name == "Batman"
    assert issue.series.volume == 1
    assert issue.series.year_began == 1940
    assert issue.number == "1"
    assert issue.issue == "Batman #1"
    assert issue.cover_date.year == 2024
    assert issue.store_date is not None
    assert issue.modified.year == 2024


def test_pull_list_issue_optional_fields(basic_series_data):
    """Test PullListIssue with optional fields omitted."""
    data = {
        "id": 100,
        "series": basic_series_data,
        "number": "1",
        "issue": "Batman #1",
        "cover_date": "2024-01-01",
        "modified": "2024-01-01T12:00:00Z",
    }
    issue = PullListIssue(**data)
    assert issue.store_date is None
    assert issue.image is None


def test_pull_list_issue_missing_required_field(basic_series_data):
    """Test PullListIssue with missing required field."""
    with pytest.raises(ValidationError):
        PullListIssue(id=100, series=basic_series_data)  # type: ignore


# PullListSeriesDetail tests
def test_pull_list_series_detail_valid_data():
    """Test PullListSeriesDetail model with valid data."""
    data = {
        "id": 1,
        "series": "Death of the Inhumans (2018)",
        "year_began": 2018,
        "year_end": 2018,
        "volume": 1,
        "modified": "2024-12-27T11:29:08.281134-05:00",
    }
    detail = PullListSeriesDetail(**data)
    assert detail.id == 1
    assert detail.name == "Death of the Inhumans (2018)"
    assert detail.year_began == 2018
    assert detail.year_end == 2018
    assert detail.volume == 1


def test_pull_list_series_detail_ongoing_series():
    """Test PullListSeriesDetail with an ongoing series (year_end=None)."""
    data = {
        "id": 2,
        "series": "Batman",
        "year_began": 1940,
        "year_end": None,
        "volume": 1,
        "modified": "2024-01-01T12:00:00Z",
    }
    detail = PullListSeriesDetail(**data)
    assert detail.year_end is None


# PullListSeries tests
def test_pull_list_series_valid_data():
    """Test PullListSeries model with valid data."""
    data = {
        "id": 6,
        "series": {
            "id": 1,
            "series": "Death of the Inhumans (2018)",
            "year_began": 2018,
            "year_end": 2018,
            "volume": 1,
            "modified": "2024-12-27T11:29:08.281134-05:00",
        },
        "added_on": "2026-05-20T16:46:36.044123-04:00",
    }
    entry = PullListSeries(**data)
    assert entry.id == 6
    assert entry.series.id == 1
    assert entry.series.name == "Death of the Inhumans (2018)"
    assert entry.series.year_began == 2018
    assert entry.series.year_end == 2018
    assert isinstance(entry.added_on, datetime)
    assert entry.added_on.year == 2026


def test_pull_list_series_missing_required_field():
    """Test PullListSeries with missing required field."""
    with pytest.raises(ValidationError):
        PullListSeries(
            id=1,
            series={
                "id": 10,
                "series": "Batman",
                "year_began": 1940,
                "volume": 1,
                "modified": "2024-01-01T12:00:00Z",
            },
        )  # type: ignore

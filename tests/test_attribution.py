"""Tests for the attribution module."""

import pytest
from pydantic import ValidationError

from mokkari.schemas.arc import Arc
from mokkari.schemas.attribution import Attribution


def test_attribution_creation() -> None:
    """Test creating an Attribution."""
    attribution = Attribution(source="Wikipedia", url="https://en.wikipedia.org/wiki/Batman")
    assert attribution.source == "Wikipedia"
    assert str(attribution.url) == "https://en.wikipedia.org/wiki/Batman"


def test_attribution_invalid_url() -> None:
    """Test that an invalid URL raises a ValidationError."""
    with pytest.raises(ValidationError):
        Attribution(source="Wikipedia", url="not-a-url")


def test_attribution_missing_fields() -> None:
    """Test that missing required fields raise a ValidationError."""
    with pytest.raises(ValidationError):
        Attribution(source="Wikipedia")


def test_resource_with_attribution() -> None:
    """Test that a detail resource parses its attribution list."""
    arc = Arc(
        id=2,
        name="The Witching Hour",
        desc="A DC Comics crossover event.",
        modified="2019-06-23T15:13:19.432378-04:00",
        resource_url="https://metron.cloud/arc/witching-hour/",
        attribution=[
            {"source": "Grand Comics Database", "url": "https://www.comics.org/"},
            {"source": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Witching_Hour"},
        ],
    )
    assert [a.source for a in arc.attribution] == ["Grand Comics Database", "Wikipedia"]


def test_resource_without_attribution() -> None:
    """Test that attribution defaults to an empty list (e.g. POST/PATCH responses)."""
    arc = Arc(
        id=2,
        name="The Witching Hour",
        desc="",
        modified="2019-06-23T15:13:19.432378-04:00",
        resource_url="https://metron.cloud/arc/witching-hour/",
    )
    assert arc.attribution == []

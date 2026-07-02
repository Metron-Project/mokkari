"""Test Issues module.

This module contains tests for Issue objects.
"""

import json
from datetime import date
from decimal import Decimal

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.schemas.issue import Issue
from mokkari.session import Session

_MODIFIED = "2019-06-23T15:13:19.432378-04:00"

_BASE_ISSUE = {
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
    "modified": _MODIFIED,
}

_MARVEL_PUBLISHER = {"id": 1, "name": "Marvel"}

_DEATH_SERIES = {
    "id": 1,
    "name": "Death of the Inhumans",
    "sort_name": "Death of the Inhumans",
    "volume": 1,
    "year_began": 2018,
    "series_type": {"id": 11, "name": "Limited Series"},
    "genres": [],
}


def test_imprint_issue() -> None:
    """Test issue from an imprint."""
    sandman = Issue(
        **{
            **_BASE_ISSUE,
            "id": 46182,
            "number": "1",
            "cover_date": "1989-01-01",
            "publisher": {"id": 2, "name": "DC Comics"},
            "imprint": {"id": 1, "name": "Vertigo Comics"},
            "series": {
                "id": 3315,
                "name": "The Sandman",
                "sort_name": "Sandman",
                "volume": 1,
                "year_began": 1989,
                "series_type": {"id": 1, "name": "Ongoing Series"},
                "genres": [],
            },
            "resource_url": "https://metron.cloud/issue/sandman-1989-1/",
        }
    )
    assert sandman.imprint.id == 1
    assert sandman.imprint.name == "Vertigo Comics"


def test_issue_with_rating() -> None:
    """Test issue with a rating."""
    ff = Issue(
        **{
            **_BASE_ISSUE,
            "id": 51658,
            "number": "47",
            "alt_number": "692",
            "cover_date": "2022-11-01",
            "store_date": "2022-09-21",
            "publisher": _MARVEL_PUBLISHER,
            "series": {
                "id": 100,
                "name": "Fantastic Four",
                "sort_name": "Fantastic Four",
                "volume": 7,
                "year_began": 2018,
                "series_type": {"id": 1, "name": "Ongoing Series"},
                "genres": [{"id": 10, "name": "Super-Hero"}],
            },
            "rating": {"id": 3, "name": "Teen"},
            "resource_url": "https://metron.cloud/issue/fantastic-four-2018-47/",
        }
    )
    assert ff.publisher.id == 1
    assert ff.publisher.name == "Marvel"
    assert ff.imprint is None
    assert ff.series.name == "Fantastic Four"
    assert ff.series.volume == 7
    assert ff.series.year_began == 2018
    assert ff.number == "47"
    assert ff.alt_number == "692"
    assert ff.rating.id == 3
    assert ff.rating.name == "Teen"
    assert ff.cover_date == date(2022, 11, 1)
    assert ff.store_date == date(2022, 9, 21)
    assert ff.series.genres[0].id == 10
    assert ff.series.genres[0].name == "Super-Hero"
    assert ff.resource_url.__str__() == "https://metron.cloud/issue/fantastic-four-2018-47/"


def test_known_issue() -> None:
    """Test for a known issue."""
    death = Issue(
        **{
            **_BASE_ISSUE,
            "id": 1,
            "number": "1",
            "name": ["Chapter One: Vox"],
            "cover_date": "2018-09-01",
            "store_date": "2018-07-04",
            "price": "4.99",
            "image": "https://static.metron.cloud/media/issue/2018/11/11/6497376-01.jpg",
            "publisher": _MARVEL_PUBLISHER,
            "series": _DEATH_SERIES,
            "characters": [{"id": 1, "name": "Black Bolt", "modified": _MODIFIED}],
            "teams": [{"id": 1, "name": "Inhumans", "modified": _MODIFIED}],
            "credits": [{"id": 1, "creator": "Donny Cates", "role": []}],
            "universes": [{"id": 1, "name": "Earth 616", "modified": _MODIFIED}],
            "resource_url": "https://metron.cloud/issue/death-of-the-inhumans-2018-1/",
        }
    )
    assert death.publisher.name == "Marvel"
    assert death.series.name == "Death of the Inhumans"
    assert death.series.volume == 1
    assert death.story_titles[0] == "Chapter One: Vox"
    assert death.cover_date == date(2018, 9, 1)
    assert death.store_date == date(2018, 7, 4)
    assert death.price == Decimal("4.99")
    assert not death.sku
    assert (
        death.image.__str__() == "https://static.metron.cloud/media/issue/2018/11/11/6497376-01.jpg"
    )
    assert len(death.characters) > 0
    assert len(death.teams) > 0
    assert len(death.credits) > 0
    assert death.teams[0].name == "Inhumans"
    assert death.teams[0].id == 1
    assert any(item.name == "Earth 616" for item in death.universes)
    assert (
        death.resource_url.__str__() == "https://metron.cloud/issue/death-of-the-inhumans-2018-1/"
    )


def test_issue_with_price_and_sku() -> None:
    """Test issue with price & sku values."""
    die_16 = Issue(
        **{
            **_BASE_ISSUE,
            "id": 36860,
            "number": "16",
            "cover_date": "2021-08-01",
            "store_date": "2021-08-25",
            "price": "3.99",
            "sku": "JUN210207",
            "publisher": {"id": 3, "name": "Image Comics"},
            "series": {
                "id": 1,
                "name": "Die",
                "sort_name": "Die",
                "volume": 1,
                "year_began": 2018,
                "series_type": {"id": 1, "name": "Ongoing Series"},
                "genres": [],
            },
            "resource_url": "https://metron.cloud/issue/die-2018-16/",
        }
    )
    assert die_16.price == Decimal("3.99")
    assert die_16.sku == "JUN210207"
    assert die_16.cover_date == date(2021, 8, 1)
    assert die_16.store_date == date(2021, 8, 25)


def test_issue_without_store_date() -> None:
    """Test issue that does not have a store date."""
    spidey = Issue(
        **{
            **_BASE_ISSUE,
            "id": 31047,
            "number": "1",
            "name": ["A Night on the Prowl!"],
            "cover_date": "1980-10-01",
            "store_date": None,
            "publisher": _MARVEL_PUBLISHER,
            "series": {
                "id": 1,
                "name": "The Spectacular Spider-Man",
                "sort_name": "Spectacular Spider-Man",
                "volume": 1,
                "year_began": 1976,
                "series_type": {"id": 1, "name": "Ongoing Series"},
                "genres": [],
            },
            "credits": [{"id": 1, "creator": "Dennis O'Neil", "role": []}],
            "characters": [{"id": 1, "name": "Spider-Man", "modified": _MODIFIED}],
            "resource_url": "https://metron.cloud/issue/spectacular-spider-man-1976-1/",
        }
    )
    assert spidey.publisher.name == "Marvel"
    assert spidey.series.name == "The Spectacular Spider-Man"
    assert spidey.series.volume == 1
    assert spidey.story_titles[0] == "A Night on the Prowl!"
    assert spidey.cover_date == date(1980, 10, 1)
    assert spidey.store_date is None
    assert "Dennis O'Neil" in [c.creator for c in spidey.credits]
    assert "Spider-Man" in [c.name for c in spidey.characters]


def test_issue_without_story_title() -> None:
    """Test an issue that does not have a story title."""
    redemption = Issue(
        **{
            **_BASE_ISSUE,
            "id": 30662,
            "number": "1",
            "cover_date": "2021-05-01",
            "store_date": "2021-05-19",
            "publisher": {"id": 10, "name": "AWA Studios"},
            "series": {
                "id": 1,
                "name": "Redemption",
                "sort_name": "Redemption",
                "volume": 1,
                "year_began": 2021,
                "series_type": {"id": 1, "name": "Limited Series"},
                "genres": [],
            },
            "credits": [{"id": 1, "creator": "Christa Faust", "role": []}],
            "resource_url": "https://metron.cloud/issue/redemption-2021-1/",
        }
    )
    assert redemption.publisher.name == "AWA Studios"
    assert redemption.series.name == "Redemption"
    assert redemption.series.volume == 1
    assert len(redemption.story_titles) == 0
    assert redemption.cover_date == date(2021, 5, 1)
    assert redemption.store_date == date(2021, 5, 19)
    assert "Christa Faust" in [c.creator for c in redemption.credits]


def test_issue_with_variant_price() -> None:
    """Test an issue that has variants with prices."""
    black_cat = Issue(
        **{
            **_BASE_ISSUE,
            "id": 156270,
            "number": "1",
            "cover_date": "2023-01-01",
            "publisher": _MARVEL_PUBLISHER,
            "series": {
                "id": 1,
                "name": "Black Cat",
                "sort_name": "Black Cat",
                "volume": 1,
                "year_began": 2023,
                "series_type": {"id": 1, "name": "Ongoing Series"},
                "genres": [],
            },
            "variants": [
                {
                    "name": "Cover B",
                    "price": "3.99",
                    "sku": "NOV220001",
                    "upc": "",
                    "image": "https://static.metron.cloud/media/variants/2023/01/black-cat-1b.jpg",
                }
            ],
            "resource_url": "https://metron.cloud/issue/black-cat-2023-1/",
        }
    )
    assert len(black_cat.variants) > 0
    assert black_cat.variants[0].price == Decimal("3.99")


def test_issueslist(talker: Session) -> None:
    """Test the IssueList."""
    data = {
        "count": 3,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 6730,
                "series": {"id": 1, "name": "Action Comics", "volume": 1, "year_began": 2011},
                "number": "1",
                "issue": "Action Comics (2011) #1",
                "cover_date": "2011-11-01",
                "cover_hash": "abc123",
                "modified": _MODIFIED,
            },
            {
                "id": 6731,
                "series": {"id": 1, "name": "Action Comics", "volume": 1, "year_began": 2011},
                "number": "2",
                "issue": "Action Comics (2011) #2",
                "cover_date": "2011-12-01",
                "cover_hash": "def456",
                "modified": _MODIFIED,
            },
            {
                "id": 6732,
                "series": {"id": 1, "name": "Action Comics", "volume": 1, "year_began": 2011},
                "number": "3",
                "issue": "Action Comics (2011) #3",
                "cover_date": "2012-01-01",
                "cover_hash": "ghi789",
                "modified": _MODIFIED,
            },
        ],
    }
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/issue/", text=json.dumps(data))
        issues = talker.issues_list({"series_name": "action comics", "series_year_began": 2011})
    issue_iter = iter(issues)
    assert next(issue_iter).id == 6730
    assert next(issue_iter).id == 6731
    assert next(issue_iter).id == 6732
    assert len(issues) == 3
    assert issues[2].id == 6732


def test_issueslist_with_params(talker: Session) -> None:
    """Test the IssueList with params given."""
    data = {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 100,
                "series": {"id": 1, "name": "Kang", "volume": 1, "year_began": 2021},
                "number": "1",
                "issue": "Kang The Conqueror (2021) #1",
                "cover_date": "2021-10-01",
                "cover_hash": "abc123",
                "modified": _MODIFIED,
            },
            {
                "id": 101,
                "series": {"id": 1, "name": "Kang", "volume": 1, "year_began": 2021},
                "number": "2",
                "issue": "Kang The Conqueror (2021) #2",
                "cover_date": "2021-11-01",
                "cover_hash": "def456",
                "modified": _MODIFIED,
            },
        ],
    }
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/issue/", text=json.dumps(data))
        issues = talker.issues_list(params={"series_name": "Kang"})
    assert len(issues) == 2
    assert issues[1].issue_name == "Kang The Conqueror (2021) #2"
    assert issues[1].cover_date == date(2021, 11, 1)


def test_issue_with_upc_sku_price() -> None:
    """Test issue with upc, sku, and price values."""
    usca_3 = Issue(
        **{
            **_BASE_ISSUE,
            "id": 36812,
            "number": "3",
            "cover_date": "2021-09-01",
            "price": "4.99",
            "price_currency": "USD",
            "sku": "JUN210696",
            "upc": "75960620100600311",
            "publisher": _MARVEL_PUBLISHER,
            "series": {
                "id": 1,
                "name": "The United States of Captain America",
                "sort_name": "United States of Captain America",
                "volume": 1,
                "year_began": 2021,
                "series_type": {"id": 6, "name": "Limited Series"},
                "genres": [],
            },
            "resource_url": "https://metron.cloud/issue/united-states-of-captain-america-2021-3/",
        }
    )
    assert usca_3.series.name == "The United States of Captain America"
    assert usca_3.number == "3"
    assert usca_3.price_currency == "USD"
    assert usca_3.price == Decimal("4.99")
    assert usca_3.sku == "JUN210696"
    assert usca_3.upc == "75960620100600311"


def test_issue_without_upc_sku_price() -> None:
    """Test issue without upc, sku, and price values."""
    bullets = Issue(
        **{
            **_BASE_ISSUE,
            "id": 89134,
            "number": "1",
            "cover_date": "2022-01-01",
            "publisher": _MARVEL_PUBLISHER,
            "series": {
                "id": 1,
                "name": "Bullets",
                "sort_name": "Bullets",
                "volume": 1,
                "year_began": 2022,
                "series_type": {"id": 1, "name": "Limited Series"},
                "genres": [],
            },
            "resource_url": "https://metron.cloud/issue/bullets-2022-1/",
        }
    )
    assert bullets.price is None
    assert bullets.price_currency == ""
    assert bullets.sku == ""
    assert bullets.upc == ""


def test_issue_with_reprints() -> None:
    """Test issue with reprint information."""
    wf = Issue(
        **{
            **_BASE_ISSUE,
            "id": 45025,
            "number": "228",
            "cover_date": "1975-03-01",
            "price": ".6",
            "publisher": {"id": 2, "name": "DC Comics"},
            "series": {
                "id": 1,
                "name": "World's Finest Comics",
                "sort_name": "World's Finest Comics",
                "volume": 1,
                "year_began": 1941,
                "series_type": {"id": 1, "name": "Ongoing Series"},
                "genres": [],
            },
            "reprints": [
                {"id": 35086, "issue": "Action Comics (1938) #193"},
                {"id": 3645, "issue": "Aquaman (1962) #12"},
                {"id": 43328, "issue": "The Brave and the Bold (1955) #58"},
                {"id": 99999, "issue": "Superman (1939) #50"},
            ],
            "resource_url": "https://metron.cloud/issue/worlds-finest-comics-1941-228/",
        }
    )
    assert wf.series.name == "World's Finest Comics"
    assert wf.number == "228"
    assert wf.cover_date == date(1975, 3, 1)
    assert wf.price == Decimal(".6")
    assert len(wf.reprints) == 4
    assert wf.reprints[0].id == 35086
    assert wf.reprints[0].issue == "Action Comics (1938) #193"
    assert wf.reprints[1].id == 3645
    assert wf.reprints[1].issue == "Aquaman (1962) #12"
    assert wf.reprints[2].id == 43328
    assert wf.reprints[2].issue == "The Brave and the Bold (1955) #58"


def test_issue_with_variants() -> None:
    """Test issue with variant data."""
    paprika = Issue(
        **{
            **_BASE_ISSUE,
            "id": 37094,
            "number": "2",
            "cover_date": "2021-09-01",
            "store_date": "2021-09-01",
            "price": "3.99",
            "sku": "JUN210256",
            "page": 32,
            "publisher": {"id": 3, "name": "Image Comics"},
            "series": {
                "id": 2511,
                "name": "Mirka Andolfo's Sweet Paprika",
                "sort_name": "Mirka Andolfo's Sweet Paprika",
                "volume": 1,
                "year_began": 2021,
                "series_type": {"id": 11, "name": "Limited Series"},
                "genres": [{"id": 1, "name": "Romance"}],
            },
            "credits": [{"id": i, "creator": f"Creator {i}", "role": []} for i in range(1, 10)],
            "variants": [
                {
                    "name": "Cover B Sejic",
                    "price": None,
                    "sku": "JUN210257",
                    "upc": "",
                    "image": "https://static.metron.cloud/media/variants/2021/08/26/sweet-paprika-2b.jpg",
                },
                {
                    "name": "Cover C March",
                    "price": None,
                    "sku": "JUN210258",
                    "upc": "",
                    "image": "https://static.metron.cloud/media/variants/2021/08/26/sweet-paprika-2c.jpg",
                },
                {
                    "name": "Cover D",
                    "price": None,
                    "sku": "JUN210259",
                    "upc": "",
                    "image": "https://static.metron.cloud/media/variants/2021/08/26/sweet-paprika-2d.jpg",
                },
                {
                    "name": "Cover E",
                    "price": None,
                    "sku": "JUN210260",
                    "upc": "",
                    "image": "https://static.metron.cloud/media/variants/2021/08/26/sweet-paprika-2e.jpg",
                },
            ],
            "resource_url": "https://metron.cloud/issue/sweet-paprika-2021-2/",
        }
    )
    assert paprika.series.id == 2511
    assert paprika.series.name == "Mirka Andolfo's Sweet Paprika"
    assert paprika.series.sort_name == "Mirka Andolfo's Sweet Paprika"
    assert paprika.series.volume == 1
    assert paprika.series.series_type.name == "Limited Series"
    assert paprika.series.series_type.id == 11
    assert len(paprika.series.genres) == 1
    assert paprika.number == "2"
    assert paprika.cover_date == date(2021, 9, 1)
    assert paprika.store_date == date(2021, 9, 1)
    assert paprika.price == Decimal("3.99")
    assert paprika.sku == "JUN210256"
    assert paprika.page_count == 32
    assert len(paprika.credits) == 9
    assert len(paprika.variants) == 4
    assert paprika.variants[0].name == "Cover B Sejic"
    assert paprika.variants[0].sku == "JUN210257"
    assert (
        paprika.variants[0].image.__str__()
        == "https://static.metron.cloud/media/variants/2021/08/26/sweet-paprika-2b.jpg"
    )
    assert paprika.variants[1].name == "Cover C March"
    assert paprika.variants[1].sku == "JUN210258"
    assert (
        paprika.variants[1].image.__str__()
        == "https://static.metron.cloud/media/variants/2021/08/26/sweet-paprika-2c.jpg"
    )


def test_issue_with_page_count() -> None:
    """Test issue that has a page count."""
    gr = Issue(
        **{
            **_BASE_ISSUE,
            "id": 8118,
            "number": "1",
            "cover_date": "2020-02-01",
            "store_date": "2019-12-18",
            "page": 40,
            "upc": "75960609672500111",
            "publisher": _MARVEL_PUBLISHER,
            "series": {
                "id": 1,
                "name": "Revenge of the Cosmic Ghost Rider",
                "sort_name": "Revenge of the Cosmic Ghost Rider",
                "volume": 1,
                "year_began": 2019,
                "series_type": {"id": 6, "name": "Limited Series"},
                "genres": [],
            },
            "resource_url": "https://metron.cloud/issue/revenge-of-the-cosmic-ghost-rider-2019-1/",
        }
    )
    assert gr.page_count == 40
    assert gr.number == "1"
    assert gr.upc == "75960609672500111"
    assert gr.cover_date == date(2020, 2, 1)
    assert gr.store_date == date(2019, 12, 18)
    assert gr.series.name == "Revenge of the Cosmic Ghost Rider"
    assert gr.series.volume == 1


def test_issue_genre() -> None:
    """Test issue with genre."""
    tt = Issue(
        **{
            **_BASE_ISSUE,
            "id": 49491,
            "number": "1",
            "cover_date": "2011-11-01",
            "store_date": "2011-09-28",
            "price": "2.99",
            "upc": "76194130522600111",
            "page": 36,
            "publisher": {"id": 2, "name": "DC Comics"},
            "series": {
                "id": 1,
                "name": "Teen Titans",
                "sort_name": "Teen Titans",
                "volume": 1,
                "year_began": 2011,
                "series_type": {"id": 1, "name": "Ongoing Series"},
                "genres": [{"id": 10, "name": "Super-Hero"}],
            },
            "resource_url": "https://metron.cloud/issue/teen-titans-2011-1/",
        }
    )
    assert len(tt.series.genres) > 0
    assert tt.series.genres[0].name == "Super-Hero"
    assert tt.cover_date == date(2011, 11, 1)
    assert tt.store_date == date(2011, 9, 28)
    assert tt.upc == "76194130522600111"
    assert tt.page_count == 36
    assert tt.price == Decimal("2.99")


def test_tpb() -> None:
    """Test a TPB."""
    hos = Issue(
        **{
            **_BASE_ISSUE,
            "id": 49622,
            "number": "1",
            "title": "The Butcher's Mark",
            "cover_date": "2022-04-01",
            "price": "14.99",
            "sku": "FEB220718",
            "upc": "9781684158164",
            "publisher": {"id": 5, "name": "BOOM! Studios"},
            "series": {
                "id": 1,
                "name": "Something is Killing the Children",
                "sort_name": "Something is Killing the Children",
                "volume": 1,
                "year_began": 2019,
                "series_type": {"id": 4, "name": "Trade Paperback"},
                "genres": [],
            },
            "reprints": [
                {"id": 1, "issue": "Something is Killing the Children (2019) #1"},
                {"id": 2, "issue": "Something is Killing the Children (2019) #2"},
                {"id": 3, "issue": "Something is Killing the Children (2019) #3"},
                {"id": 4, "issue": "Something is Killing the Children (2019) #4"},
                {"id": 5, "issue": "Something is Killing the Children (2019) #5"},
            ],
            "resource_url": "https://metron.cloud/issue/sitc-tpb-1/",
        }
    )
    assert hos.collection_title == "The Butcher's Mark"
    assert hos.price == Decimal("14.99")
    assert hos.sku == "FEB220718"
    assert hos.upc == "9781684158164"
    assert len(hos.reprints) == 5


def test_bad_issue(talker: Session) -> None:
    """Test for a non-existant issue."""
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/issue/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.issue(-1)


def test_multi_page_results(talker: Session) -> None:
    """Test for multi page results."""
    page1 = {
        "count": 4,
        "next": "https://metron.cloud/api/issue/?page=2&series_name=action+comics",
        "previous": None,
        "results": [
            {
                "id": 1,
                "series": {"id": 1, "name": "Action Comics", "volume": 1, "year_began": 1938},
                "number": "1",
                "issue": "Action Comics (1938) #1",
                "cover_date": "1938-06-01",
                "cover_hash": "abc123",
                "modified": _MODIFIED,
            },
            {
                "id": 2,
                "series": {"id": 1, "name": "Action Comics", "volume": 1, "year_began": 1938},
                "number": "2",
                "issue": "Action Comics (1938) #2",
                "cover_date": "1938-07-01",
                "cover_hash": "def456",
                "modified": _MODIFIED,
            },
        ],
    }
    page2 = {
        "count": 4,
        "next": None,
        "previous": "https://metron.cloud/api/issue/?series_name=action+comics",
        "results": [
            {
                "id": 903,
                "series": {"id": 1, "name": "Action Comics", "volume": 1, "year_began": 1938},
                "number": "903",
                "issue": "Action Comics (1938) #903",
                "cover_date": "2011-09-01",
                "cover_hash": "ghi789",
                "modified": _MODIFIED,
            },
            {
                "id": 904,
                "series": {"id": 1, "name": "Action Comics", "volume": 1, "year_began": 1938},
                "number": "904",
                "issue": "Action Comics (1938) #904",
                "cover_date": "2011-10-01",
                "cover_hash": "jkl012",
                "modified": _MODIFIED,
            },
        ],
    }
    with requests_mock.Mocker() as r:
        r.get("https://metron.cloud/api/issue/", text=json.dumps(page1))
        r.get(
            "https://metron.cloud/api/issue/?page=2&series_name=action+comics",
            text=json.dumps(page2),
        )
        issues = talker.issues_list({"series_name": "action comics", "series_year_began": 1938})
    assert len(issues) == 4
    assert issues[0].issue_name == "Action Comics (1938) #1"
    assert issues[0].cover_date == date(1938, 6, 1)
    assert issues[3].issue_name == "Action Comics (1938) #904"
    assert issues[3].cover_date == date(2011, 10, 1)


def test_bad_issue_validate(talker: Session) -> None:
    """Test data with invalid data."""
    # Change the 'number' field to an int, when it should be a string.
    data = {
        "id": 150,
        "publisher": {"id": 2, "name": "DC Comics"},
        "series": {"id": 25, "name": "Mister Miracle"},
        "volume": 1,
        "number": 20,
        "name": ["Eclipse"],
        "cover_date": "1977-10-01",
        "store_date": None,
        "price": None,
        "sku": "",
        "upc": "",
        "page": None,
        "desc": "Scott rescues Barda on the Moon.",
        "image": "https://static.metron.cloud/media/issue/2018/11/25/mm20.jpg",
        "arcs": [],
        "credits": [],
        "characters": [],
        "teams": [],
        "variants": [],
        "modified": _MODIFIED,
    }

    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/issue/150/",
            text=json.dumps(data),
        )

        with pytest.raises(exceptions.ApiError):
            talker.issue(150)

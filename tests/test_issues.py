"""Test Issues module.

This module contains tests for Issue objects.
"""

import json
from datetime import date
from decimal import Decimal

import pytest
import requests_mock

from mokkari import exceptions
from mokkari.session import Session


def test_imprint_issue(talker: Session) -> None:
    """Test issue from an imprint."""
    sandman = talker.issue(46182)
    assert sandman.imprint.id == 1
    assert sandman.imprint.name == "Vertigo Comics"


def test_issue_with_rating(talker: Session) -> None:
    """Test issue with a rating."""
    ff = talker.issue(51658)
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


def test_known_issue(talker: Session) -> None:
    """Test for a known issue."""
    death = talker.issue(1)
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


def test_issue_with_price_and_sku(talker: Session) -> None:
    """Test issue with price & sku values."""
    die_16 = talker.issue(36860)
    assert die_16.price == Decimal("3.99")
    assert die_16.sku == "JUN210207"
    assert die_16.cover_date == date(2021, 8, 1)
    assert die_16.store_date == date(2021, 8, 25)


def test_issue_without_store_date(talker: Session) -> None:
    """Test issue that does not have a store date."""
    spidey = talker.issue(31047)
    assert spidey.publisher.name == "Marvel"
    assert spidey.series.name == "The Spectacular Spider-Man"
    assert spidey.series.volume == 1
    assert spidey.story_titles[0] == "A Night on the Prowl!"
    assert spidey.cover_date == date(1980, 10, 1)
    assert spidey.store_date is None
    assert "Dennis O'Neil" in [c.creator for c in spidey.credits]
    assert "Spider-Man" in [c.name for c in spidey.characters]


def test_issue_without_story_title(talker: Session) -> None:
    """Test an issue that does not have a story title."""
    redemption = talker.issue(30662)
    assert redemption.publisher.name == "AWA Studios"
    assert redemption.series.name == "Redemption"
    assert redemption.series.volume == 1
    assert len(redemption.story_titles) == 0
    assert redemption.cover_date == date(2021, 5, 1)
    assert redemption.store_date == date(2021, 5, 19)
    assert "Christa Faust" in [c.creator for c in redemption.credits]


def test_issue_with_variant_price(talker: Session) -> None:
    """Test an issue that has variants with prices."""
    black_cat = talker.issue(156270)
    assert len(black_cat.variants) > 0
    assert black_cat.variants[0].price == Decimal("3.99")


def test_issueslist(talker: Session) -> None:
    """Test the IssueList."""
    issues = talker.issues_list({"series_name": "action comics", "series_year_began": 2011})
    issue_iter = iter(issues)
    assert next(issue_iter).id == 6730
    assert next(issue_iter).id == 6731
    assert next(issue_iter).id == 6732
    assert len(issues) == 57
    assert issues[2].id == 6732
    assert issues[56].issue_name == "Action Comics (2011) #52"


def test_issueslist_with_params(talker: Session) -> None:
    """Test the IssueList with params given."""
    params = {
        "series_name": "Kang",
    }
    issues = talker.issues_list(params=params)
    assert len(issues) == 7
    assert issues[1].issue_name == "Kang The Conqueror (2021) #1"
    assert issues[1].cover_date == date(2021, 10, 1)


def test_issue_with_upc_sku_price(talker: Session) -> None:
    """Test issue with upc, sku, and price values."""
    usca_3 = talker.issue(36812)
    assert usca_3.series.name == "The United States of Captain America"
    assert usca_3.number == "3"
    assert usca_3.price_currency == "USD"
    assert usca_3.price == Decimal("4.99")
    assert usca_3.sku == "JUN210696"
    assert usca_3.upc == "75960620100600311"


def test_issue_without_upc_sku_price(talker: Session) -> None:
    """Test issue without upc, sku, and price values."""
    bullets = talker.issue(89134)
    assert bullets.price is None
    assert bullets.price_currency == ""
    assert bullets.sku == ""
    assert bullets.upc == ""


def test_issue_with_reprints(talker: Session) -> None:
    """Test issue with reprint information."""
    wf = talker.issue(45025)
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


def test_issue_with_variants(talker: Session) -> None:
    """Test issue with variant data."""
    paprika = talker.issue(37094)
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


def test_issue_with_page_count(talker: Session) -> None:
    """Test issue that has a page count."""
    gr = talker.issue(8118)
    assert gr.page_count == 40
    assert gr.number == "1"
    assert gr.upc == "75960609672500111"
    assert gr.cover_date == date(2020, 2, 1)
    assert gr.store_date == date(2019, 12, 18)
    assert gr.series.name == "Revenge of the Cosmic Ghost Rider"
    assert gr.series.volume == 1


def test_issue_genre(talker: Session) -> None:
    """Test issue with genre."""
    tt = talker.issue(49491)
    assert len(tt.series.genres) > 0
    assert tt.series.genres[0].name == "Super-Hero"
    assert tt.cover_date == date(2011, 11, 1)
    assert tt.store_date == date(2011, 9, 28)
    assert tt.upc == "76194130522600111"
    assert tt.page_count == 36
    assert tt.price == Decimal("2.99")


def test_tpb(talker: Session) -> None:
    """Test a TPB."""
    hos = talker.issue(49622)
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
    issues = talker.issues_list({"series_name": "action comics", "series_year_began": 1938})
    assert len(issues) == 864
    assert issues[0].issue_name == "Action Comics (1938) #1"
    assert issues[0].cover_date == date(1938, 6, 1)
    assert issues[863].issue_name == "Action Comics (1938) #904"
    assert issues[863].cover_date == date(2011, 10, 1)


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
        "modified": "2019-06-23T15:13:18.212120-04:00",
    }

    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/issue/150/",
            text=json.dumps(data),
        )

        with pytest.raises(exceptions.ApiError):
            talker.issue(150)

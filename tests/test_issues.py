import datetime

import pytest
import requests_mock

from mokkari import exceptions, issues_list


def test_known_issue(talker):
    death = talker.issue(1)
    assert death.publisher.name == "Marvel"
    assert death.series.name == "Death of the Inhumans"
    assert death.volume == 1
    assert death.story_titles[0] == "Chapter One: Vox"
    assert death.cover_date == datetime.date(2018, 9, 1)
    assert death.store_date == datetime.date(2018, 7, 4)
    assert death.price is None
    assert not death.sku
    assert death.image == "https://static.metron.cloud/media/issue/2018/11/11/6497376-01.jpg"
    assert len(death.characters) > 0
    assert len(death.teams) > 0
    assert len(death.credits) > 0


def test_issue_with_price_and_sku(talker):
    die_16 = talker.issue(36860)
    assert die_16.price == "3.99"
    assert die_16.sku == "JUN210207"
    assert die_16.cover_date == datetime.date(2021, 8, 1)
    assert die_16.store_date == datetime.date(2021, 8, 25)


def test_issue_without_store_date(talker):
    spidey = talker.issue(31047)
    assert spidey.publisher.name == "Marvel"
    assert spidey.series.name == "The Spectacular Spider-Man"
    assert spidey.volume == 1
    assert spidey.story_titles[0] == "A Night on the Prowl!"
    assert spidey.cover_date == datetime.date(1980, 10, 1)
    assert spidey.store_date is None
    assert "Dennis O'Neil" in [c.creator for c in spidey.credits]
    assert "Spider-Man" in [c.name for c in spidey.characters]


def test_issue_without_story_title(talker):
    redemption = talker.issue(30662)
    assert redemption.publisher.name == "AWA Studios"
    assert redemption.series.name == "Redemption"
    assert redemption.volume == 1
    assert len(redemption.story_titles) == 0
    assert redemption.cover_date == datetime.date(2021, 5, 1)
    assert redemption.store_date == datetime.date(2021, 5, 19)
    assert "Christa Faust" in [c.creator for c in redemption.credits]


def test_issueslist(talker):
    issues = talker.issues_list()
    issue_iter = iter(issues)
    assert next(issue_iter).id == 32656
    assert next(issue_iter).id == 32657
    assert next(issue_iter).id == 32658
    assert len(issues) == 28
    assert issues[2].id == 32658
    assert issues[1].issue_name == "100 Bullets #2"


def test_issue_with_upc_sku_price(talker):
    usca_3 = talker.issue(36812)
    assert usca_3.series.name == "The United States of Captain America"
    assert usca_3.number == "3"
    assert usca_3.price == "4.99"
    assert usca_3.sku == "JUN210696"
    assert usca_3.upc == "75960620100600311"


def test_issue_without_upc_sku_price(talker):
    bullets = talker.issue(32662)
    assert bullets.price is None
    assert bullets.sku == ""
    assert bullets.upc == ""


def test_issue_with_variants(talker):
    paprika = talker.issue(37094)
    assert paprika.series.id == 2511
    assert paprika.series.name == "Mirka Andolfo's Sweet Paprika"
    assert paprika.volume == 1
    assert paprika.number == "2"
    assert paprika.cover_date == datetime.date(2021, 9, 1)
    assert paprika.store_date == datetime.date(2021, 9, 1)
    assert len(paprika.credits) == 3
    assert len(paprika.variants) == 4
    assert paprika.variants[0].name == "Cover B Sejic"
    assert paprika.variants[0].sku == "JUN210257"
    assert (
        paprika.variants[0].image
        == "https://static.metron.cloud/media/variants/2021/08/26/sweet-paprika-2b.jpg"
    )
    assert paprika.variants[1].name == "Cover C March"
    assert paprika.variants[1].sku == "JUN210258"
    assert (
        paprika.variants[1].image
        == "https://static.metron.cloud/media/variants/2021/08/26/sweet-paprika-2c.jpg"
    )


def test_bad_issue(talker):
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/issue/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.issue(-1)


def test_bad_response_data():
    with pytest.raises(exceptions.ApiError):
        issues_list.IssuesList({"results": {"volume": "1"}})

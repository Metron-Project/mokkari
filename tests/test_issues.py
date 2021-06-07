import datetime

import pytest
import requests_mock
from mokkari import exceptions, issues_list


def test_known_issue(talker):
    death = talker.issue(1)
    assert death.publisher.name == "Marvel"
    assert death.series.name == "Death of the Inhumans"
    assert death.volume == 1
    assert death.name[0] == "Chapter One: Vox"
    assert death.cover_date == datetime.date(2018, 9, 1)
    assert death.store_date == datetime.date(2018, 7, 4)
    assert (
        death.image
        == "https://static.metron.cloud/media/issue/2018/11/11/6497376-01.jpg"
    )
    assert len(death.characters) > 0
    assert len(death.teams) > 0
    assert len(death.credits) > 0


def test_issue_without_store_date(talker):
    spidey = talker.issue(31047)
    assert spidey.publisher.name == "Marvel"
    assert spidey.series.name == "The Spectacular Spider-Man"
    assert spidey.volume == 1
    assert spidey.name[0] == "A Night on the Prowl!"
    assert spidey.cover_date == datetime.date(1980, 10, 1)
    assert spidey.store_date is None
    assert "Dennis O'Neil" in [c.creator for c in spidey.credits]
    assert "Spider-Man" in [c.name for c in spidey.characters]


def test_issue_without_story_title(talker):
    redemption = talker.issue(30662)
    assert redemption.publisher.name == "AWA Studios"
    assert redemption.series.name == "Redemption"
    assert redemption.volume == 1
    assert len(redemption.name) == 0
    assert redemption.cover_date == datetime.date(2021, 5, 1)
    assert redemption.store_date == datetime.date(2021, 5, 19)
    assert "Christa Faust" in [c.creator for c in redemption.credits]


def test_issueslist(talker):
    issues = talker.issues_list()
    issue_iter = iter(issues)
    assert next(issue_iter).id == 16909
    assert next(issue_iter).id == 16910
    assert next(issue_iter).id == 16911
    assert len(issues) == 28
    assert issues[2].id == 16911


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

import datetime

import pytest
import requests_mock

from mokkari import creators_list, exceptions


def test_known_creator(talker):
    jack = talker.creator(3)
    assert jack.name == "Jack Kirby"
    assert jack.birth == datetime.date(1917, 8, 28)
    assert jack.death == datetime.date(1994, 2, 6)
    assert (
        jack.image
        == "https://static.metron.cloud/media/creator/2018/11/11/432124-Jack_Kirby01.jpg"
    )
    assert jack.wikipedia == "Jack_Kirby"


def test_comiclist(talker):
    creators = talker.creators_list()
    creator_iter = iter(creators)
    assert next(creator_iter).name == "A. J. Jothikumar"
    assert next(creator_iter).name == "A. J. Lieberman"
    assert next(creator_iter).name == "A.J. Fierro"
    assert next(creator_iter).name == "A.J. Mendez"
    assert len(creators) == 28
    assert creators[3].name == "A.J. Mendez"


def test_bad_creator(talker):
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/creator/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.creator(-1)


def test_bad_response_data(talker):
    with pytest.raises(exceptions.ApiError):
        creators_list.CreatorsList({"results": {"name": 1}})

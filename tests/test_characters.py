import pytest
import requests_mock

from mokkari import characters_list, exceptions


def test_known_character(talker):
    black_bolt = talker.character(1)
    assert black_bolt.name == "Black Bolt"
    assert (
        black_bolt.image
        == "https://static.metron.cloud/media/character/2018/11/11/black-bolt.jpg"
    )
    assert black_bolt.wikipedia == "Black_Bolt"
    assert len(black_bolt.creators) == 2
    assert len(black_bolt.teams) == 2


def test_characterlist(talker):
    character = talker.characters_list()
    character_iter = iter(character)
    assert next(character_iter).name == "'Mazing Man"
    assert next(character_iter).name == "0101"
    assert next(character_iter).name == "2 Face 2"
    assert len(character) == 28
    assert character[2].name == "2 Face 2"


def test_bad_character(talker):
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/character/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.character(-1)


def test_bad_response_data(talker):
    with pytest.raises(exceptions.ApiError):
        characters_list.CharactersList({"results": {"name": 1}})

import pytest
import requests_mock

from mokkari import exceptions, teams_list


def test_known_team(talker):
    inhumans = talker.team(1)
    assert inhumans.name == "Inhumans"
    assert inhumans.image == "https://static.metron.cloud/media/team/2018/11/11/Inhumans.jpg"
    assert inhumans.wikipedia == "Inhumans"
    assert len(inhumans.creators) == 2


def test_teamlist(talker):
    teams = talker.teams_list()
    team_iter = iter(teams)
    assert next(team_iter).name == "A-Force"
    assert next(team_iter).name == "A.I.M."
    assert next(team_iter).name == "A.R.G.U.S."
    assert len(teams) == 28
    assert teams[2].name == "A.R.G.U.S."


def test_bad_team(talker):
    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/team/-1/",
            text='{"response_code": 404, "detail": "Not found."}',
        )
        with pytest.raises(exceptions.ApiError):
            talker.team(-1)


def test_bad_response_data():
    with pytest.raises(exceptions.ApiError):
        teams_list.TeamsList({"results": {"name": 1}})

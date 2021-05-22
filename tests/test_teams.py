import pytest
from mokkari import exceptions, teams_list


def test_known_team(talker):
    inhumans = talker.team(1)
    assert inhumans.name == "Inhumans"
    assert (
        inhumans.image
        == "https://static.metron.cloud/media/team/2018/11/11/Inhumans.jpg"
    )
    assert inhumans.wikipedia == "Inhumans"
    assert len(inhumans.creators) == 2


def test_teamlist(talker):
    teams = talker.teams_list()
    assert len(teams.teams) > 0


def test_bad_team(talker):
    with pytest.raises(exceptions.ApiError):
        talker.team(-1)


def test_bad_response_data():
    with pytest.raises(exceptions.ApiError):
        teams_list.TeamsList({"results": {"name": 1}})

import pytest
from mokkari import arcs_list, exceptions


def test_known_arc(talker):
    heroes = talker.arc(1)
    assert heroes.name == "Heroes In Crisis"
    assert (
        heroes.image
        == "https://static.metron.cloud/media/arc/2018/11/12/heroes-in-crisis.jpeg"
    )


def test_arcslist(talker):
    arcs = talker.arcs_list()
    assert len(arcs.arcs) > 0


def test_bad_arc(talker):
    with pytest.raises(exceptions.ApiError):
        talker.arc(-1)


def test_bad_response_data():
    with pytest.raises(exceptions.ApiError):
        arcs_list.ArcsList({"results": {"name": 1}})

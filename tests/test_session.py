# ruff: noqa: S106
"""Test Session module.

This module contains tests for Session objects.
"""

import datetime as dt
import inspect
import json
import typing
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
import requests_mock
from requests.adapters import DEFAULT_POOLSIZE, HTTPAdapter
from requests.exceptions import ConnectionError as ConnError

import mokkari.session as session_module
from mokkari import exceptions, rate_limit
from mokkari.rate_limit import HeaderPacedRateLimiter
from mokkari.schemas.arc import Arc
from mokkari.schemas.character import CharacterPost
from mokkari.schemas.collection import (
    CollectionAddItem,
    CollectionUpdate,
)
from mokkari.schemas.creator import CreatorPost
from mokkari.schemas.series import SeriesPost
from mokkari.schemas.wish_list import (
    AcquireWishListItem,
)
from mokkari.session import Session


@pytest.fixture
def dummy_cache():
    # Arrange
    # Provide a dummy cache object with get and store methods
    class DummyCache:
        def __init__(self):
            self._store = {}

        def get(self, key):
            return self._store.get(key)

        def store(self, key, value, *, resource, kind):
            self._store[key] = value

    return DummyCache()


def test_session_init_raises_without_a_token() -> None:
    """Test that Session raises AuthenticationError for a missing or empty token."""
    with pytest.raises(exceptions.AuthenticationError):
        Session(None)  # type: ignore

    with pytest.raises(exceptions.AuthenticationError):
        Session("")


def test_session_init_keeps_token_out_of_header() -> None:
    """Test that the token isn't stored in the header dict, which gets logged."""
    s = Session(api_token="abc123")

    assert "Authorization" not in s.header


def test_execute_http_request_sends_bearer_header() -> None:
    """Test that _execute_http_request sends the token as a Bearer header."""
    token_session = Session(api_token="abc123")

    with requests_mock.Mocker() as r:
        r.get("https://test.com/api/issue/1", json={})
        token_session._execute_http_request(
            "GET", "https://test.com/api/issue/1", headers=token_session.header
        )

    assert r.last_request.headers["Authorization"] == "Bearer abc123"


def test_execute_http_request_ignores_netrc(tmp_path: Path, monkeypatch) -> None:
    """Test that a netrc entry for the host doesn't replace the Bearer header."""
    netrc = tmp_path / ".netrc"
    netrc.write_text("machine test.com login user password pass\n")
    netrc.chmod(0o600)
    monkeypatch.setenv("NETRC", str(netrc))
    token_session = Session(api_token="abc123")

    with requests_mock.Mocker() as r:
        r.get("https://test.com/api/issue/1", json={})
        token_session._execute_http_request(
            "GET", "https://test.com/api/issue/1", headers=token_session.header
        )

    assert r.last_request.headers["Authorization"] == "Bearer abc123"


def test_session_reuses_a_single_http_session(session: Session, monkeypatch) -> None:
    """Test that successive requests all go through the one pooled requests.Session."""
    http_session = session._http
    mock_request = MagicMock(return_value=MagicMock(headers={}))
    monkeypatch.setattr(http_session, "request", mock_request)
    module_level_request = MagicMock()
    monkeypatch.setattr(requests, "request", module_level_request)

    session._execute_http_request("GET", "https://test.com/api/issue/1")
    session._execute_http_request("GET", "https://test.com/api/issue/2")

    assert session._http is http_session
    assert mock_request.call_count == 2
    module_level_request.assert_not_called()


@pytest.mark.parametrize("url", ["https://test.com/api/", "http://127.0.0.1:8000/api/"])
def test_http_session_pool_fits_concurrent_threads(session: Session, url: str) -> None:
    """Test that the pool holds enough connections that threads sharing a Session reuse them."""
    adapter = session._http.get_adapter(url)
    assert isinstance(adapter, HTTPAdapter)
    pool_kw = adapter.poolmanager.connection_pool_kw

    assert pool_kw["maxsize"] == session_module.HTTP_POOL_MAXSIZE
    assert session_module.HTTP_POOL_MAXSIZE > DEFAULT_POOLSIZE


def test_http_session_drops_cookies(session: Session) -> None:
    """Test that Set-Cookie headers are never stored or replayed on later requests."""
    with requests_mock.Mocker(session=session._http) as m:
        m.get(
            "https://test.com/api/issue/1/",
            headers={"Set-Cookie": "sessionid=abc; Path=/"},
            json={"id": 1},
        )
        m.get("https://test.com/api/issue/2/", json={"id": 2})

        session._request_data("GET", "https://test.com/api/issue/1/")
        session._request_data("GET", "https://test.com/api/issue/2/")

        assert list(session._http.cookies) == []
        assert "Cookie" not in m.last_request.headers


def test_session_close_closes_http_session(session: Session, monkeypatch) -> None:
    """Test that close() releases the pooled connections."""
    mock_close = MagicMock()
    monkeypatch.setattr(session._http, "close", mock_close)

    session.close()

    mock_close.assert_called_once_with()


def test_session_context_manager_closes_on_exit(monkeypatch) -> None:
    """Test that the context manager returns the session and closes it on exit."""
    with Session(api_token="abc123") as s:
        mock_close = MagicMock()
        monkeypatch.setattr(s._http, "close", mock_close)
        assert isinstance(s, Session)
        mock_close.assert_not_called()

    mock_close.assert_called_once_with()


def test_session_context_manager_closes_on_error(monkeypatch) -> None:
    """Test that the context manager closes the session even when the body raises."""
    s = Session(api_token="abc123")
    mock_close = MagicMock()
    monkeypatch.setattr(s._http, "close", mock_close)

    def use_session() -> None:
        with s:
            msg = "boom"
            raise RuntimeError(msg)

    with pytest.raises(RuntimeError):
        use_session()

    mock_close.assert_called_once_with()


def test_session_usable_after_close(session: Session) -> None:
    """Test that close() is idempotent and a closed session reopens connections on demand."""
    session.close()
    session.close()

    with requests_mock.Mocker(session=session._http) as m:
        m.get("https://test.com/api/issue/1/", json={"id": 1})
        assert session._request_data("GET", "https://test.com/api/issue/1/") == {"id": 1}


@pytest.mark.parametrize(
    ("endpoint", "params", "resp", "expected", "case_id"),
    [
        (["creator", 1], None, {"id": 1, "name": "John"}, {"id": 1, "name": "John"}, "no_params"),
        (
            ["creator", 2],
            {"foo": "bar"},
            {"id": 2, "name": "Jane"},
            {"id": 2, "name": "Jane"},
            "with_params",
        ),
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test__get_happy_path(  # noqa: PLR0913, PLR0917
    session: Session,
    endpoint: list[str | int],
    params: dict[str, str | int] | None,
    resp: dict[str, str | int],
    expected: dict[str, str | int],
    case_id: str,
) -> None:
    # Arrange
    with (
        patch.object(session._cache_coordinator, "get", return_value=None),
        patch.object(session, "_request_data", return_value=resp),
        patch.object(session._cache_coordinator, "store") as save_cache,
    ):
        # Act
        result = session._get(endpoint, params)
        # Assert
        assert result == expected
        save_cache.assert_called_once()


def test__get_returns_cached(session: Session) -> None:
    # Arrange
    cached = {"id": 99, "name": "Cached"}
    with patch.object(session._cache_coordinator, "get", return_value=cached):
        # Act
        result = session._get(["creator", 99])
        # Assert
        assert result == cached


def test__get_raises_api_error_on_detail(session: Session) -> None:
    # Arrange: a 200 whose body is an error detail
    with requests_mock.Mocker() as r:
        r.get(session.api_url.format("creator/1"), json={"detail": "fail"})
        # Act / Assert
        with pytest.raises(exceptions.ApiError):
            session._get(["creator", 1])


@pytest.mark.parametrize(
    ("method", "endpoint", "data", "resp", "case_id"),
    [
        ("POST", ["creator"], CreatorPost(name="Bar"), {"id": 1}, "post_creator"),
        ("PATCH", ["creator", "1"], CreatorPost(name="Baz"), {"id": 1}, "patch_creator"),
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test__send(  # noqa: PLR0913, PLR0917
    session: Session,
    method: str,
    endpoint: list[str | int],
    data: CreatorPost,
    resp: dict[str, int],
    case_id: str,
) -> None:
    # Arrange
    url = session._url(endpoint)
    with requests_mock.Mocker() as r:
        r.register_uri(method, url, json=resp)
        # Act
        result = session._send(method, endpoint, data)
        # Assert
        assert result == resp
        assert r.call_count == 1


@pytest.mark.parametrize(
    ("helper", "call"),
    [
        ("_send", lambda s: s.creator_post(CreatorPost(name="John"))),
        ("_send", lambda s: s.creator_patch(1, CreatorPost(name="John"))),
        ("_send", lambda s: s.character_post(CharacterPost(name="Batman"))),
        ("_send", lambda s: s.character_patch(1, CharacterPost(name="Batman"))),
        ("_get_results", lambda s: s.character_issues_list(1)),
    ],
    ids=["creator_post", "creator_patch", "character_post", "character_patch", "issues_list"],
)
def test_invalid_response_raises_api_error(session: Session, helper: str, call) -> None:
    """A response missing required fields fails validation and is reported as an ApiError."""
    # Arrange: what Metron sent back lacks every field but the id
    resp = {"results": [{"id": 1}], "next": None} if helper == "_get_results" else {"id": 1}
    with (
        patch.object(session, helper, return_value=resp),
        pytest.raises(exceptions.ApiError),
    ):
        # Act
        call(session)


def test_collection_patch_api_error(session: Session) -> None:
    # Arrange
    data = CollectionUpdate(rating=4)
    with (
        patch.object(session, "_send", side_effect=exceptions.ApiError("fail")),
        pytest.raises(exceptions.ApiError),
    ):
        session.collection_patch(1, data)


def test_collection_add_api_error(session: Session) -> None:
    # Arrange
    add_request = CollectionAddItem(issue_id=1)
    with (
        patch.object(session, "_send", side_effect=exceptions.ApiError("fail")),
        pytest.raises(exceptions.ApiError),
    ):
        session.collection_add(add_request)


def test_collection_delete(session: Session) -> None:
    # Arrange
    with patch.object(session, "_send_void") as mock_send_void:
        # Act
        result = session.collection_delete(1)
        # Assert
        assert result is None
        mock_send_void.assert_called_once_with("DELETE", ["collection", 1])


@pytest.mark.parametrize(
    ("result", "has_next", "case_id"),
    [
        ({"results": [{"id": 1}], "next": None}, False, "no_next"),
        ({"results": [{"id": 1}], "next": "url2"}, True, "has_next"),
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test__get_results(session, result, has_next, case_id):
    # Arrange
    with patch.object(session, "_fetch", return_value=(result, False)):
        if has_next:
            with patch.object(session, "_retrieve_all_results", return_value=result) as ret:
                # Act
                out = session._get_results(["foo"])
                # Assert
                assert out == result
                ret.assert_called_once()
        else:
            # Act
            out = session._get_results(["foo"])
            # Assert
            assert out == result


def test__retrieve_all_results_skips_cache_reads(session: Session) -> None:
    """Following pages are always fetched, then stored, never read from the cache."""
    # Arrange
    data = {"results": [1], "next": "url2"}
    resp2 = {"results": [2], "next": None}
    with (
        patch.object(session._cache_coordinator, "get") as cache_get,
        patch.object(session, "_request_data", return_value=resp2),
        patch.object(session._cache_coordinator, "store") as cache_store,
    ):
        # Act
        out = session._retrieve_all_results(data, "foo")
        # Assert
        assert out["results"] == [1, 2]
        cache_get.assert_not_called()
        cache_store.assert_called_once_with("url2", resp2, "foo", "list", invalidations=0)


def test__retrieve_all_results_without_cache(session: Session) -> None:
    # Arrange
    data = {"results": [1], "next": "url2"}
    resp2 = {"results": [2], "next": None}
    with (
        patch.object(session._cache_coordinator, "get", return_value=None),
        patch.object(session, "_request_data", return_value=resp2),
        patch.object(session._cache_coordinator, "store"),
    ):
        # Act
        out = session._retrieve_all_results(data, "foo")
        # Assert
        assert out["results"] == [1, 2]


def test__retrieve_all_results_raises_after_repeated_429s_without_retry_after(
    session: Session,
) -> None:
    # Arrange
    data = {"results": [1], "next": "url2"}
    error = exceptions.RateLimitError("limited", retry_after=0)
    with (
        patch.object(session._cache_coordinator, "get", return_value=None),
        patch.object(session, "_request_data", side_effect=error) as request,
        patch("mokkari.session.time.sleep") as sleep,
    ):
        # Act
        with pytest.raises(exceptions.RateLimitError):
            session._retrieve_all_results(data, "foo")
        # Assert
        assert request.call_count == session_module.MAX_UNTIMED_RATE_LIMIT_RETRIES + 1
        # No Retry-After to honour, so each retry waits a full burst window rather than
        # firing back-to-back.
        assert sleep.call_args_list == [((rate_limit.DEFAULT_BURST_PERIOD,),)] * (
            session_module.MAX_UNTIMED_RATE_LIMIT_RETRIES
        )


def test__retrieve_all_results_untimed_retry_count_resets_after_a_page(session: Session) -> None:
    # Arrange: more header-less 429s in total than the cap, but never that many in a row
    data = {"results": [1], "next": "url2"}
    error = exceptions.RateLimitError("limited", retry_after=0)
    page2 = {"results": [2], "next": "url3"}
    page3 = {"results": [3], "next": None}
    responses = [error, error, error, page2, error, error, error, page3]
    with (
        patch.object(session._cache_coordinator, "get", return_value=None),
        patch.object(session, "_request_data", side_effect=responses),
        patch.object(session._cache_coordinator, "store"),
        patch("mokkari.session.time.sleep"),
    ):
        # Act
        out = session._retrieve_all_results(data, "foo")
        # Assert
        assert out["results"] == [1, 2, 3]


def test__retrieve_all_results_keeps_retrying_429s_that_have_retry_after(
    session: Session,
) -> None:
    # Arrange: a real Retry-After is a wait worth honouring, so it isn't held to the small
    # untimed cap, only to the larger overall one
    data = {"results": [1], "next": "url2"}
    error = exceptions.RateLimitError("limited", retry_after=5)
    attempts = session_module.MAX_UNTIMED_RATE_LIMIT_RETRIES + 3
    responses = [error] * attempts + [{"results": [2], "next": None}]
    with (
        patch.object(session._cache_coordinator, "get", return_value=None),
        patch.object(session, "_request_data", side_effect=responses),
        patch.object(session._cache_coordinator, "store"),
        patch("mokkari.session.time.sleep") as sleep,
    ):
        # Act
        out = session._retrieve_all_results(data, "foo")
        # Assert
        assert out["results"] == [1, 2]
        assert sleep.call_args_list == [((5,),)] * attempts


def test__retrieve_all_results_raises_after_repeated_429s_with_retry_after(
    session: Session,
) -> None:
    # Arrange: another client keeps the account saturated, so every retry is rejected again
    data = {"results": [1], "next": "url2"}
    error = exceptions.RateLimitError("limited", retry_after=5)
    with (
        patch.object(session._cache_coordinator, "get", return_value=None),
        patch.object(session, "_request_data", side_effect=error) as request,
        patch("mokkari.session.time.sleep") as sleep,
    ):
        # Act
        with pytest.raises(exceptions.RateLimitError):
            session._retrieve_all_results(data, "foo")
        # Assert
        assert request.call_count == session_module.MAX_RATE_LIMIT_RETRIES + 1
        assert sleep.call_args_list == [((5,),)] * session_module.MAX_RATE_LIMIT_RETRIES


def test__retrieve_all_results_with_rate_limiter_retries_429_without_sleeping(
    session: Session,
) -> None:
    # Arrange: the limiter blocks in acquire(), so the loop shouldn't also sleep
    session.rate_limiter = HeaderPacedRateLimiter()
    data = {"results": [1], "next": "url2"}
    error = session_module._ServerRateLimitError("limited", retry_after=5)
    responses = [error, {"results": [2], "next": None}]
    with (
        patch.object(session._cache_coordinator, "get", return_value=None),
        patch.object(session, "_request_data", side_effect=responses) as request,
        patch.object(session._cache_coordinator, "store"),
        patch("mokkari.session.time.sleep") as sleep,
    ):
        # Act
        out = session._retrieve_all_results(data, "foo")
        # Assert
        assert out["results"] == [1, 2]
        assert request.call_count == 2
        sleep.assert_not_called()


def test__retrieve_all_results_with_rate_limiter_caps_retries_of_a_non_blocking_limiter(
    session: Session,
) -> None:
    # Arrange: a limiter whose acquire() returns at once never paces the retries
    session.rate_limiter = HeaderPacedRateLimiter()
    data = {"results": [1], "next": "url2"}
    error = session_module._ServerRateLimitError("limited", retry_after=5)
    with (
        patch.object(session._cache_coordinator, "get", return_value=None),
        patch.object(session, "_request_data", side_effect=error) as request,
        patch("mokkari.session.time.sleep") as sleep,
    ):
        # Act
        with pytest.raises(exceptions.RateLimitError):
            session._retrieve_all_results(data, "foo")
        # Assert
        assert request.call_count == session_module.MAX_RATE_LIMIT_RETRIES + 1
        sleep.assert_not_called()


def test__retrieve_all_results_with_rate_limiter_retry_cap_resets_after_a_page(
    session: Session,
) -> None:
    # Arrange: more 429s in total than the cap, but never that many in a row
    session.rate_limiter = HeaderPacedRateLimiter()
    data = {"results": [1], "next": "url2"}
    error = session_module._ServerRateLimitError("limited", retry_after=5)
    run = [error] * session_module.MAX_RATE_LIMIT_RETRIES
    responses = [*run, {"results": [2], "next": "url3"}, *run, {"results": [3], "next": None}]
    with (
        patch.object(session._cache_coordinator, "get", return_value=None),
        patch.object(session, "_request_data", side_effect=responses),
        patch.object(session._cache_coordinator, "store"),
    ):
        # Act
        out = session._retrieve_all_results(data, "foo")
        # Assert
        assert out["results"] == [1, 2, 3]


def test__retrieve_all_results_with_rate_limiter_propagates_limiter_refusal(
    session: Session,
) -> None:
    # Arrange: the limiter refusing a request (daily window exhausted) isn't a 429 to retry
    session.rate_limiter = HeaderPacedRateLimiter()
    data = {"results": [1], "next": "url2"}
    error = exceptions.RateLimitError("daily limit", retry_after=3600)
    with (
        patch.object(session._cache_coordinator, "get", return_value=None),
        patch.object(session, "_request_data", side_effect=error) as request,
        patch("mokkari.session.time.sleep") as sleep,
    ):
        # Act / Assert
        with pytest.raises(exceptions.RateLimitError) as exc_info:
            session._retrieve_all_results(data, "foo")
        assert exc_info.value.retry_after == 3600
        assert request.call_count == 1
        sleep.assert_not_called()


def test__retrieve_all_results_with_rate_limiter_end_to_end(session: Session, monkeypatch) -> None:
    """A real 429 is backed off by the limiter (not the loop), then the page is retried."""
    limiter = HeaderPacedRateLimiter()
    session.rate_limiter = limiter

    def response(status_code: int, headers: dict[str, str], body: bytes) -> requests.Response:
        resp = requests.Response()
        resp.status_code = status_code
        resp.headers.update(headers)
        resp._content = body
        return resp

    responses = [
        response(429, {"Retry-After": "0.01"}, b"{}"),
        response(200, {}, b'{"results": [2], "next": null}'),
    ]
    monkeypatch.setattr(session._http, "request", lambda *_a, **_k: responses.pop(0))
    data = {"results": [1], "next": "https://test.com/api/issue/?page=2"}

    with (
        patch("mokkari.session.time.sleep") as sleep,
        patch.object(limiter, "acquire", wraps=limiter.acquire) as acquire,
        patch.object(limiter, "on_rate_limited", wraps=limiter.on_rate_limited) as backed_off,
    ):
        out = session._retrieve_all_results(data, "foo")

    # The limiter was told about the 429 and gated the retry; the loop didn't sleep itself.
    assert out["results"] == [1, 2]
    backed_off.assert_called_once_with(0.01)
    assert acquire.call_count == 2
    sleep.assert_not_called()


def test__send_void_raises_server_rate_limit_error_on_429(session: Session, monkeypatch) -> None:
    # Arrange
    resp = requests.Response()
    resp.status_code = 429
    resp.headers["Retry-After"] = "7"
    resp._content = b"{}"
    monkeypatch.setattr(session._http, "request", lambda *_a, **_k: resp)
    # Act / Assert: tagged like the 429s raised for GET/POST/PATCH, so callers can tell
    # a rejection by Metron from one raised locally before sending
    with pytest.raises(session_module._ServerRateLimitError) as exc_info:
        session._send_void("DELETE", ["collection", 1])
    assert exc_info.value.retry_after == 7


def test__request_data_get(monkeypatch, session, make_response):
    # Arrange
    monkeypatch.setattr(
        session._http, "request", lambda *a, **k: make_response(json_body={"foo": "bar"})
    )
    # Act
    out = session._request_data("GET", "url")
    # Assert
    assert out == {"foo": "bar"}


def test__execute_write_post_list(monkeypatch, session, make_response):
    # Arrange
    monkeypatch.setattr(
        session._http, "request", lambda *a, **k: make_response(201, json_body={"foo": "bar"})
    )
    # Act
    data = [MagicMock(model_dump=lambda: {"a": 1})]
    out = session._execute_write("POST", ["credit"], data)
    # Assert
    assert out.json() == {"foo": "bar"}


def test__execute_write_post_with_image(monkeypatch, session, tmp_path, make_response):
    # Arrange
    monkeypatch.setattr(
        session._http, "request", lambda *a, **k: make_response(201, json_body={"foo": "bar"})
    )
    img_file = tmp_path / "img.png"
    img_file.write_bytes(b"abc")
    data = MagicMock(model_dump=lambda: {"image": str(img_file)})
    # Act
    out = session._execute_write("POST", ["creator"], data)
    # Assert
    assert out.json() == {"foo": "bar"}


def test__request_data_connection_error(monkeypatch, session):
    # Arrange
    def raise_conn(*a, **k):
        raise ConnError

    monkeypatch.setattr(session._http, "request", raise_conn)
    # Act & Assert
    with pytest.raises(exceptions.ApiError):
        session._request_data("GET", "url")


def test__request_data_detail(monkeypatch, session, make_response):
    # Arrange
    # Test successful request (200)
    monkeypatch.setattr(
        session._http, "request", lambda *a, **k: make_response(json_body={"foo": "bar"})
    )
    out = session._request_data("GET", "url")
    assert out == {"foo": "bar"}

    # Test another successful status code (201)
    monkeypatch.setattr(
        session._http, "request", lambda *a, **k: make_response(201, json_body={"foo": "bar"})
    )
    out = session._request_data("GET", "url")
    assert out == {"foo": "bar"}

    # Test client error (400) - should raise ApiError
    monkeypatch.setattr(
        session._http, "request", lambda *a, **k: make_response(400, json_body={"foo": "bar"})
    )
    with pytest.raises(exceptions.ApiError):
        session._request_data("GET", "url")


def test_cache_coordinator_get_without_cache(session: Session) -> None:
    # Act
    out = session._cache_coordinator.get("key", "series")
    # Assert
    assert out is None


# ============================================================================
# _prepare_request_payload Tests
# ============================================================================


def test__prepare_request_payload_none_data(session: Session) -> None:
    """No payload when data is None."""
    _header, files, data_dict = session._prepare_request_payload(None)
    assert files is None
    assert data_dict is None


def test__prepare_request_payload_json_excludes_none_fields(session: Session) -> None:
    """None fields must not appear in the JSON body for non-image models."""
    data = SeriesPost(gcd_id=12345)
    _, files, data_dict = session._prepare_request_payload(data)
    assert files is None
    assert isinstance(data_dict, str)
    parsed = json.loads(data_dict)
    assert parsed == {"gcd_id": 12345}


def test__prepare_request_payload_partial_series_patch_only_sends_set_field(
    session: Session,
) -> None:
    """A SeriesPost with only gcd_id set must produce a single-key payload.

    This is the regression test for the bug where PATCH /series/<id>/ failed with
    '400 This field may not be null' because all None fields were serialised.
    """
    data = SeriesPost(gcd_id=99)
    _, _, data_dict = session._prepare_request_payload(data)
    assert isinstance(data_dict, str)
    parsed = json.loads(data_dict)
    assert parsed == {"gcd_id": 99}


def test__prepare_request_payload_all_set_fields_are_included(session: Session) -> None:
    """Fields that are explicitly set must be present in the JSON body."""
    data = SeriesPost(name="Batman", sort_name="Batman", volume=1, year_began=1940, gcd_id=7)
    _, _, data_dict = session._prepare_request_payload(data)
    assert isinstance(data_dict, str)
    parsed = json.loads(data_dict)
    assert parsed["name"] == "Batman"
    assert parsed["sort_name"] == "Batman"
    assert parsed["volume"] == 1
    assert parsed["year_began"] == 1940
    assert parsed["gcd_id"] == 7
    assert "publisher" not in parsed


def test__prepare_request_payload_image_model_uses_multipart_and_strips_none(
    session: Session, tmp_path: Path
) -> None:
    """Image-field models must still use multipart form data with None values stripped."""
    img_file = tmp_path / "cover.png"
    img_file.write_bytes(b"fakepng")
    data = MagicMock(model_dump=lambda: {"name": "Test Arc", "image": str(img_file), "desc": None})
    _, files, data_dict = session._prepare_request_payload(data)
    assert files is not None
    assert "image" in files
    assert isinstance(data_dict, dict)
    assert data_dict.get("name") == "Test Arc"
    assert "desc" not in data_dict


def test__prepare_request_payload_image_model_no_image_file(session: Session) -> None:
    """Image-field model with image=None must still use multipart (no file uploaded)."""
    data = MagicMock(model_dump=lambda: {"name": "Test Arc", "image": None, "desc": None})
    _, files, data_dict = session._prepare_request_payload(data)
    assert files is None
    assert isinstance(data_dict, dict)
    assert data_dict.get("name") == "Test Arc"
    assert "desc" not in data_dict
    assert "image" not in data_dict


# ============================================================================
# Cache Status (X-Cache) Tests
# ============================================================================


def test_last_cache_status_defaults_to_none(session: Session) -> None:
    """A fresh session has no observed cache status until a request completes."""
    assert session.last_cache_status is None


def test_update_cache_status_parses_header(session: Session) -> None:
    """The X-Cache header is captured into the session's last-observed cache status."""
    session._update_cache_status({"X-Cache": "HIT"})

    assert session.last_cache_status == "HIT"


def test_update_cache_status_resets_when_header_absent(session: Session) -> None:
    """A response missing the X-Cache header means that endpoint isn't cached.

    Unlike rate-limit headers, X-Cache is per-endpoint (Metron only adds it on
    cached paths), so a missing header should reset the status to None rather
    than keep showing a stale HIT/MISS from an earlier, cached endpoint.
    """
    session._update_cache_status({"X-Cache": "HIT"})

    session._update_cache_status({})

    assert session.last_cache_status is None


def test_request_data_updates_cache_status_from_response(
    session: Session, monkeypatch, make_response
) -> None:
    """A successful response's X-Cache header should update the session's cache status."""
    monkeypatch.setattr(
        session._http,
        "request",
        lambda *a, **k: make_response(
            json_body={"id": 1, "name": "Test"}, headers={"X-Cache": "MISS"}
        ),
    )

    result = session._request_data("GET", "https://test.com/api/issue/1")

    assert result == {"id": 1, "name": "Test"}
    assert session.last_cache_status == "MISS"


def test_request_data_resets_cache_status_for_uncached_endpoint(
    session: Session,
    monkeypatch,
    make_response,
) -> None:
    """A subsequent request to an uncached endpoint should clear a prior HIT/MISS."""
    session._last_cache_status = "HIT"

    monkeypatch.setattr(
        session._http, "request", lambda *a, **k: make_response(json_body={"id": 1, "name": "Test"})
    )

    session._request_data("GET", "https://test.com/api/pull_list")

    assert session.last_cache_status is None


# ============================================================================
# Conditional Request (If-Modified-Since) Tests
# ============================================================================


def test_if_modified_since_returns_none_on_304(
    session: Session, monkeypatch, make_response
) -> None:
    """Test that passing if_modified_since returns None when server responds 304."""
    # Arrange
    monkeypatch.setattr(session._http, "request", lambda *a, **k: make_response(304))

    # Act
    result = session.arc(1, if_modified_since=dt.datetime(2025, 1, 1, tzinfo=dt.UTC))

    # Assert
    assert result is None


def test_if_modified_since_sends_header(session: Session, monkeypatch, make_response) -> None:
    """Test that if_modified_since sends the correctly formatted If-Modified-Since header."""
    # Arrange
    captured_kwargs = {}

    def mock_request(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return make_response(304)

    monkeypatch.setattr(session._http, "request", mock_request)

    # Act
    session.arc(
        1,
        if_modified_since=dt.datetime(2025, 1, 1, 12, 0, 0, tzinfo=dt.UTC),
    )

    # Assert — verify the header was formatted as RFC 7231
    assert captured_kwargs["headers"]["If-Modified-Since"] == "Wed, 01 Jan 2025 12:00:00 GMT"


def test_if_modified_since_naive_datetime_treated_as_utc(
    session: Session, monkeypatch, make_response
) -> None:
    """Test that a naive datetime (no tzinfo) is treated as UTC."""
    # Arrange
    captured_kwargs = {}

    def mock_request(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return make_response(304)

    monkeypatch.setattr(session._http, "request", mock_request)

    # Act — pass a naive datetime
    session.arc(1, if_modified_since=dt.datetime(2025, 6, 15, 8, 30, 0))  # noqa: DTZ001

    # Assert — should be formatted as UTC
    assert captured_kwargs["headers"]["If-Modified-Since"] == "Sun, 15 Jun 2025 08:30:00 GMT"


def test_if_modified_since_non_utc_timezone_converted(
    session: Session, monkeypatch, make_response
) -> None:
    """Test that a non-UTC timezone-aware datetime is converted to UTC for the header."""
    # Arrange
    captured_kwargs = {}

    def mock_request(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return make_response(304)

    monkeypatch.setattr(session._http, "request", mock_request)

    # Create a US/Central-like timezone (UTC-6)
    cst = dt.timezone(dt.timedelta(hours=-6))
    # 2025-01-01 06:00:00 CST == 2025-01-01 12:00:00 UTC
    dt_cst = dt.datetime(2025, 1, 1, 6, 0, 0, tzinfo=cst)

    # Act
    session.arc(1, if_modified_since=dt_cst)

    # Assert — should be converted to UTC
    assert captured_kwargs["headers"]["If-Modified-Since"] == "Wed, 01 Jan 2025 12:00:00 GMT"


def _arc_json(name: str) -> dict[str, object]:
    """Return a valid arc detail response named ``name``."""
    return {
        "id": 1,
        "name": name,
        "desc": "",
        "resource_url": "https://metron.cloud/arc/1/",
        "modified": "2025-01-01T00:00:00Z",
    }


def test_if_modified_since_returns_resource_on_200(
    session: Session, monkeypatch, make_response
) -> None:
    """Test that passing if_modified_since returns the resource when data has changed."""
    # Arrange
    monkeypatch.setattr(
        session._http, "request", lambda *a, **k: make_response(json_body=_arc_json("Updated"))
    )

    # Act
    result = session.arc(1, if_modified_since=dt.datetime(2025, 1, 1, tzinfo=dt.UTC))

    # Assert
    assert isinstance(result, Arc)
    assert result.name == "Updated"


def test_if_modified_since_bypasses_cache(
    session: Session, dummy_cache, monkeypatch, make_response
) -> None:
    """Test that if_modified_since skips the cache entirely."""
    # Arrange
    session.cache = dummy_cache
    dummy_cache.store(
        "https://metron.cloud/api/arc/1/", _arc_json("Cached"), resource="arc", kind="detail"
    )
    monkeypatch.setattr(
        session._http, "request", lambda *a, **k: make_response(json_body=_arc_json("Fresh"))
    )

    # Act
    result = session.arc(1, if_modified_since=dt.datetime(2025, 1, 1, tzinfo=dt.UTC))

    # Assert — got the fresh data, not the cached
    assert result is not None
    assert result.name == "Fresh"


def test_without_if_modified_since_uses_cache(session: Session, dummy_cache, monkeypatch) -> None:
    """Test that without if_modified_since, the normal cache flow is used."""
    # Arrange
    session.cache = dummy_cache
    dummy_cache.store(
        "https://metron.cloud/api/arc/1/", _arc_json("Cached"), resource="arc", kind="detail"
    )
    request = MagicMock()
    monkeypatch.setattr(session._http, "request", request)

    # Act
    result = session.arc(1)

    # Assert — served from the cache without a request
    assert result.name == "Cached"
    request.assert_not_called()


def test_wish_list_acquire_item(session: Session) -> None:
    # Arrange
    acquire_request = AcquireWishListItem(
        purchase_price=Decimal("9.99"), purchase_store="Local Comic Shop"
    )
    with patch.object(session, "_send_void") as mock_send_void:
        # Act
        result = session.wish_list_acquire_item(10, acquire_request)
        # Assert
        assert result is None
        mock_send_void.assert_called_once_with(
            "POST",
            ["wish_list", "items", 10, "acquire"],
            acquire_request,
            also_invalidates=("collection",),
        )


def test_wish_list_remove_item(session: Session) -> None:
    # Arrange
    with patch.object(session, "_send_void") as mock_send_void:
        # Act
        result = session.wish_list_remove_item(10)
        # Assert
        assert result is None
        mock_send_void.assert_called_once_with("DELETE", ["wish_list", "items", 10, "remove"])


@pytest.mark.parametrize(
    ("method", "endpoint", "item", "count_field"),
    [
        (
            "pull_list",
            "pull_list",
            {
                "id": 1,
                "series_count": 3,
                "series_url": "https://metron.cloud/api/pull_list/series/",
            },
            "series_count",
        ),
        (
            "wish_list",
            "wish_list",
            {"id": 1, "item_count": 5, "items_url": "https://metron.cloud/api/wish_list/items/"},
            "item_count",
        ),
    ],
    ids=["pull_list", "wish_list"],
)
def test_user_list_returns_the_only_result(
    session: Session, method: str, endpoint: str, item: dict[str, Any], count_field: str
) -> None:
    """The pull list and wish list are read from a one-item list."""
    body = {"next": None, "results": [{**item, "modified": "2024-01-01T12:00:00Z"}]}
    with requests_mock.Mocker() as r:
        r.get(session.api_url.format(endpoint), json=body)
        result = getattr(session, method)()

    assert result.id == 1
    assert getattr(result, count_field) == item[count_field]


@pytest.mark.parametrize(
    ("method", "endpoint"),
    [("pull_list", "pull_list"), ("wish_list", "wish_list")],
    ids=["pull_list", "wish_list"],
)
def test_user_list_raises_api_error_when_empty(
    session: Session, method: str, endpoint: str
) -> None:
    """An empty list is reported as an ApiError rather than an IndexError."""
    with requests_mock.Mocker() as r:
        r.get(session.api_url.format(endpoint), json={"next": None, "results": []})
        with pytest.raises(exceptions.ApiError, match="Metron returned no"):
            getattr(session, method)()


def test_public_method_annotations_resolve_at_runtime() -> None:
    """Every public method's type hints resolve, for tools that inspect them at runtime."""
    methods = [
        member
        for name, member in inspect.getmembers(Session, inspect.isfunction)
        if not name.startswith("_")
    ]
    assert methods
    for method in methods:
        typing.get_type_hints(method)


def test_rate_limit_header_names_still_importable_from_session() -> None:
    """The header-name constants that moved to rate_limit can still be imported from session."""
    for name in (
        "HEADER_BURST_LIMIT",
        "HEADER_BURST_REMAINING",
        "HEADER_BURST_RESET",
        "HEADER_SUSTAINED_LIMIT",
        "HEADER_SUSTAINED_REMAINING",
        "HEADER_SUSTAINED_RESET",
    ):
        assert getattr(session_module, name) == getattr(rate_limit, name)


def test_list_validation_uses_overridden_validate_response() -> None:
    """A subclass's _validate_response is used for list calls, as for detail calls."""
    seen: list[Any] = []

    class LoggingSession(Session):
        @staticmethod
        def _validate_response(resp: Any, adapter_class: type) -> Any:
            seen.append(adapter_class)
            return Session._validate_response(resp, adapter_class)

    s = LoggingSession("abc123", cache=None, user_agent="pytest", dev_mode=False)

    with requests_mock.Mocker() as r:
        r.get(
            "https://metron.cloud/api/series_type/",
            json={"count": 1, "next": None, "previous": None, "results": [{"id": 1, "name": "A"}]},
        )
        result = s.series_type_list()

    assert [item.name for item in result] == ["A"]
    assert len(seen) == 1
    assert typing.get_origin(seen[0]) is list

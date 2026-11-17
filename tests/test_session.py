# ruff: noqa: S106
"""Test Session module.

This module contains tests for Session objects.
"""

import datetime as dt
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
import requests_mock
from requests.adapters import DEFAULT_POOLSIZE, HTTPAdapter
from requests.exceptions import ConnectionError as ConnError, TooManyRedirects

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
def session() -> Session:
    # Arrange
    # Provide a Session with dummy credentials and no cache
    return Session("abc123", cache=None, user_agent="pytest", dev_mode=False)


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
# Rate Limiting Tests
# ============================================================================
#
# Metron's sustained (daily) limit is dynamic per user (higher for
# OpenCollective donors), so Session tracks rate limits reactively from the
# X-RateLimit-* response headers instead of a fixed local quota.


def test_rate_limit_status_defaults_to_unknown(session: Session) -> None:
    """A fresh session has no observed rate-limit state until a request completes."""
    status = session.rate_limit_status
    assert status.burst == rate_limit.RateLimitWindow()
    assert status.sustained == rate_limit.RateLimitWindow()


def test_update_rate_limit_status_parses_headers(session: Session) -> None:
    """Headers from a response are parsed into the session's rate-limit status."""
    headers = {
        "X-RateLimit-Burst-Limit": "20",
        "X-RateLimit-Burst-Remaining": "19",
        "X-RateLimit-Burst-Reset": "1700000060",
        "X-RateLimit-Sustained-Limit": "10000",
        "X-RateLimit-Sustained-Remaining": "9999",
        "X-RateLimit-Sustained-Reset": "1700086400",
    }

    session._update_rate_limit_status(headers)

    status = session.rate_limit_status
    assert status.burst.limit == 20
    assert status.burst.remaining == 19
    assert status.burst.reset == dt.datetime.fromtimestamp(1700000060, tz=dt.UTC)
    assert status.sustained.limit == 10_000
    assert status.sustained.remaining == 9_999
    assert status.sustained.reset == dt.datetime.fromtimestamp(1700086400, tz=dt.UTC)


def test_update_rate_limit_status_ignores_response_without_headers(session: Session) -> None:
    """A response missing rate-limit headers shouldn't erase previously observed state."""
    session._update_rate_limit_status({"X-RateLimit-Burst-Limit": "20"})

    session._update_rate_limit_status({})

    assert session.rate_limit_status.burst.limit == 20


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


def test_check_rate_limit_allows_request_when_no_state_observed(session: Session) -> None:
    """Nothing is known yet, so the first request is never pre-emptively blocked."""
    session._check_rate_limit()  # should not raise


def test_check_rate_limit_allows_request_when_remaining_positive(session: Session) -> None:
    """Test that a window with remaining quota does not block."""
    reset = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=30)
    session._rate_limit_status = rate_limit.RateLimitStatus(
        burst=rate_limit.RateLimitWindow(limit=20, remaining=5, reset=reset)
    )

    session._check_rate_limit()  # should not raise


def test_check_rate_limit_raises_when_burst_exhausted(session: Session) -> None:
    """Test that an exhausted burst (minute) window raises RateLimitError."""
    reset = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=60)
    session._rate_limit_status = rate_limit.RateLimitStatus(
        burst=rate_limit.RateLimitWindow(limit=20, remaining=0, reset=reset)
    )

    with pytest.raises(exceptions.RateLimitError) as excinfo:
        session._check_rate_limit()

    error_msg = str(excinfo.value)
    assert "Rate limit exceeded" in error_msg
    assert "20 requests per minute" in error_msg
    assert "Please wait" in error_msg
    assert excinfo.value.retry_after == pytest.approx(60, abs=2)


def test_check_rate_limit_raises_when_sustained_exhausted(session: Session) -> None:
    """Test that an exhausted sustained (daily) window raises RateLimitError.

    The sustained limit here (10,000) reflects an elevated OpenCollective donor
    tier rather than the default 5,000/day, since it's read straight from
    whatever the server last reported.
    """
    reset = dt.datetime.now(dt.UTC) + dt.timedelta(days=1)
    session._rate_limit_status = rate_limit.RateLimitStatus(
        sustained=rate_limit.RateLimitWindow(limit=10_000, remaining=0, reset=reset)
    )

    with pytest.raises(exceptions.RateLimitError) as excinfo:
        session._check_rate_limit()

    error_msg = str(excinfo.value)
    assert "Rate limit exceeded" in error_msg
    assert "10,000 requests per day" in error_msg
    assert "Please wait" in error_msg
    assert excinfo.value.retry_after == pytest.approx(86_400, abs=2)


def test_check_rate_limit_blocks_request(session: Session, monkeypatch) -> None:
    """Test that an exhausted window prevents the HTTP request from being made."""
    reset = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=60)
    session._rate_limit_status = rate_limit.RateLimitStatus(
        burst=rate_limit.RateLimitWindow(limit=20, remaining=0, reset=reset)
    )

    mock_request_called = {"called": False}

    def mock_request(*args, **kwargs):
        mock_request_called["called"] = True
        return MagicMock()

    monkeypatch.setattr(session._http, "request", mock_request)

    with pytest.raises(exceptions.RateLimitError):
        session._request_data("GET", "https://test.com/api/issue/1")

    assert not mock_request_called["called"], "HTTP request should not be made when rate limited"


def test_rate_limit_allows_successful_request(session: Session, monkeypatch, make_response) -> None:
    """Test that requests proceed normally when no rate limit is exhausted."""
    # Arrange
    monkeypatch.setattr(
        session._http, "request", lambda *a, **k: make_response(json_body={"id": 1, "name": "Test"})
    )

    # Act
    result = session._request_data("GET", "https://test.com/api/issue/1")

    # Assert
    assert result == {"id": 1, "name": "Test"}


def test_request_data_updates_rate_limit_status_from_response(
    session: Session,
    monkeypatch,
    make_response,
) -> None:
    """A successful response's headers should update the session's rate-limit status."""
    monkeypatch.setattr(
        session._http,
        "request",
        lambda *a, **k: make_response(
            json_body={"id": 1, "name": "Test"},
            headers={
                "X-RateLimit-Burst-Limit": "20",
                "X-RateLimit-Burst-Remaining": "18",
                "X-RateLimit-Burst-Reset": "1700000060",
                "X-RateLimit-Sustained-Limit": "5000",
                "X-RateLimit-Sustained-Remaining": "4998",
                "X-RateLimit-Sustained-Reset": "1700086400",
            },
        ),
    )

    result = session._request_data("GET", "https://test.com/api/issue/1")

    assert result == {"id": 1, "name": "Test"}
    assert session.rate_limit_status.burst.remaining == 18
    assert session.rate_limit_status.sustained.remaining == 4998


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


def test_session_rate_limiter_defaults_to_none() -> None:
    """A Session with no rate_limiter argument has one set to None."""
    session = Session("abc123")

    assert session.rate_limiter is None


def test_execute_http_request_dispatches_to_rate_limiter_when_set(
    session: Session,
    monkeypatch,
    make_response,
) -> None:
    """When a rate_limiter is configured, it gates and observes every HTTP send."""
    calls = []

    class FakeLimiter:
        def on_rate_limited(self, retry_after):
            pass

        def acquire(self, status):
            calls.append(("acquire", status))

        def release(self, status):
            calls.append(("release", status))

    session.rate_limiter = FakeLimiter()

    monkeypatch.setattr(
        session._http,
        "request",
        lambda *a, **k: make_response(
            json_body={"id": 1}, headers={"X-RateLimit-Burst-Remaining": "19"}
        ),
    )

    result = session._request_data("GET", "https://test.com/api/issue/1")

    assert result == {"id": 1}
    assert [call for call, _ in calls] == ["acquire", "release"]
    # release is called with the status as updated by this response.
    assert calls[1][1].burst.remaining == 19


def test_execute_http_request_falls_back_to_check_rate_limit_when_no_limiter(
    session: Session, monkeypatch
) -> None:
    """With no rate_limiter set (the default), behavior is unchanged: fail fast."""
    reset = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=60)
    session._rate_limit_status = rate_limit.RateLimitStatus(
        burst=rate_limit.RateLimitWindow(limit=20, remaining=0, reset=reset)
    )

    mock_request_called = {"called": False}

    def mock_request(*args, **kwargs):
        mock_request_called["called"] = True
        return MagicMock()

    monkeypatch.setattr(session._http, "request", mock_request)

    with pytest.raises(exceptions.RateLimitError):
        session._request_data("GET", "https://test.com/api/issue/1")

    assert not mock_request_called["called"]


def test_rate_limiter_release_called_with_none_on_connection_error(
    session: Session, monkeypatch
) -> None:
    """A connection error releases the limiter's slot with status=None."""
    calls = []

    class FakeLimiter:
        def on_rate_limited(self, retry_after):
            pass

        def acquire(self, status):
            calls.append(("acquire", status))

        def release(self, status):
            calls.append(("release", status))

    session.rate_limiter = FakeLimiter()

    def mock_request(*args, **kwargs):
        msg = "boom"
        raise ConnError(msg)

    monkeypatch.setattr(session._http, "request", mock_request)

    with pytest.raises(exceptions.ApiError):
        session._request_data("GET", "https://test.com/api/issue/1")

    assert calls == [("acquire", rate_limit.RateLimitStatus()), ("release", None)]


def test_rate_limiter_release_called_on_unhandled_request_exception(
    session: Session, monkeypatch
) -> None:
    """An exception other than ConnectionError/ReadTimeout still releases the slot."""
    calls = []

    class FakeLimiter:
        def on_rate_limited(self, retry_after):
            pass

        def acquire(self, status):
            calls.append(("acquire", status))

        def release(self, status):
            calls.append(("release", status))

    session.rate_limiter = FakeLimiter()

    def mock_request(*args, **kwargs):
        msg = "too many redirects"
        raise TooManyRedirects(msg)

    monkeypatch.setattr(session._http, "request", mock_request)

    with pytest.raises(TooManyRedirects):
        session._request_data("GET", "https://test.com/api/issue/1")

    assert calls == [("acquire", rate_limit.RateLimitStatus()), ("release", None)]


def test_rate_limiter_release_called_when_status_update_raises(
    session: Session,
    monkeypatch,
    make_response,
) -> None:
    """A failure while processing response headers still releases the slot."""
    calls = []

    class FakeLimiter:
        def on_rate_limited(self, retry_after):
            pass

        def acquire(self, status):
            calls.append(("acquire", status))

        def release(self, status):
            calls.append(("release", status))

    session.rate_limiter = FakeLimiter()

    monkeypatch.setattr(
        session._http,
        "request",
        lambda *a, **k: make_response(headers={"X-RateLimit-Burst-Remaining": "not-an-int"}),
    )

    with pytest.raises(ValueError, match="invalid literal"):
        session._request_data("GET", "https://test.com/api/issue/1")

    assert [call for call, _ in calls] == ["acquire", "release"]


def test_rate_limiter_not_released_when_acquire_fails(session: Session, monkeypatch) -> None:
    """If acquire() raises, no slot was reserved, so release() must not be called."""
    calls = []

    class FakeLimiter:
        def on_rate_limited(self, retry_after):
            pass

        def acquire(self, status):
            calls.append("acquire")
            msg = "no capacity"
            raise RuntimeError(msg)

        def release(self, status):
            calls.append("release")

    session.rate_limiter = FakeLimiter()

    monkeypatch.setattr(session._http, "request", lambda *a, **k: MagicMock())

    with pytest.raises(RuntimeError, match="no capacity"):
        session._request_data("GET", "https://test.com/api/issue/1")

    assert calls == ["acquire"]


def test_rate_limiter_missing_acquire_raises_rate_limiter_error(
    session: Session, monkeypatch
) -> None:
    """A rate_limiter object missing acquire() raises RateLimiterError."""

    class NoAcquire:
        def release(self, status):
            pass

    session.rate_limiter = NoAcquire()  # pyright: ignore[reportAttributeAccessIssue]  (deliberately lacks acquire)

    monkeypatch.setattr(session._http, "request", lambda *a, **k: MagicMock())

    with pytest.raises(exceptions.RateLimiterError):
        session._request_data("GET", "https://test.com/api/issue/1")


def test_rate_limiter_missing_release_raises_rate_limiter_error(
    session: Session,
    monkeypatch,
    make_response,
) -> None:
    """A rate_limiter object missing release() raises RateLimiterError."""

    class NoRelease:
        def acquire(self, status):
            pass

    session.rate_limiter = NoRelease()  # pyright: ignore[reportAttributeAccessIssue]  (deliberately lacks release)

    monkeypatch.setattr(
        session._http, "request", lambda *a, **k: make_response(json_body={"id": 1})
    )

    with pytest.raises(exceptions.RateLimiterError):
        session._request_data("GET", "https://test.com/api/issue/1")


def test_rate_limiter_paces_concurrent_requests(monkeypatch, make_response) -> None:
    """A real HeaderPacedRateLimiter shared across threads never exceeds its window."""
    period = 0.3
    limiter = HeaderPacedRateLimiter(burst_period=period)
    paced_session = Session("abc123", user_agent="pytest", rate_limiter=limiter)
    sent: list[float] = []

    def mock_request(*args, **kwargs):
        sent.append(time.monotonic())
        time.sleep(0.02)  # widen the window so concurrent callers actually overlap
        return make_response(
            json_body={"id": 1},
            headers={"X-RateLimit-Burst-Limit": "3", "X-RateLimit-Burst-Remaining": "3"},
        )

    monkeypatch.setattr(paced_session._http, "request", mock_request)

    # Prime the limiter's burst limit before the concurrent batch starts: with
    # nothing observed yet it would let every caller straight through, since
    # a gate with no prior information can't restrict anything (the same
    # "gate opens" behavior a real client sees on its very first request).
    limiter.acquire(rate_limit.RateLimitStatus(burst=rate_limit.RateLimitWindow(limit=3)))
    limiter.release(None)

    def worker(_):
        paced_session._request_data("GET", "https://test.com/api/issue/1")

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(worker, range(10)))

    # The primed send counts against the window too, so it's part of the log
    # even though it never went through requests.request.
    assert len(sent) == 10
    sent.sort()
    for t in sent:
        assert len([x for x in sent if t <= x < t + period - 0.01]) <= 3
    assert limiter._in_flight == 0


def test_real_rate_limiter_raises_rate_limit_error_for_exhausted_daily_window(
    monkeypatch,
) -> None:
    """An exhausted daily window surfaces as RateLimitError and no HTTP request is sent."""
    limiter = HeaderPacedRateLimiter()
    paced_session = Session("abc123", user_agent="pytest", rate_limiter=limiter)
    reset = dt.datetime.now(dt.UTC) + dt.timedelta(hours=1)
    paced_session._rate_limit_status = rate_limit.RateLimitStatus(
        sustained=rate_limit.RateLimitWindow(limit=5000, remaining=0, reset=reset)
    )
    sent = []
    monkeypatch.setattr(paced_session._http, "request", lambda *a, **k: sent.append(1))

    with pytest.raises(exceptions.RateLimitError) as exc_info:
        paced_session._request_data("GET", "https://test.com/api/issue/1")

    assert exc_info.value.retry_after == pytest.approx(3600, abs=5)
    assert sent == []
    assert limiter._in_flight == 0


def test_daily_limit_429_makes_the_next_request_raise_without_sending(
    monkeypatch, make_response
) -> None:
    """A 429 carrying an exhausted daily window stops the next request before it is sent."""
    limiter = HeaderPacedRateLimiter()
    paced_session = Session("abc123", user_agent="pytest", rate_limiter=limiter)
    reset = dt.datetime.now(dt.UTC) + dt.timedelta(hours=1)
    sent = []

    def fake_request(*args, **kwargs):
        sent.append(1)
        return make_response(
            429,
            headers={
                "Retry-After": "3600",
                "X-RateLimit-Sustained-Limit": "5000",
                "X-RateLimit-Sustained-Remaining": "0",
                "X-RateLimit-Sustained-Reset": str(int(reset.timestamp())),
            },
        )

    monkeypatch.setattr(paced_session._http, "request", fake_request)

    paced_session._execute_http_request("GET", "https://test.com/api/issue/1")
    with pytest.raises(exceptions.RateLimitError) as exc_info:
        paced_session._execute_http_request("GET", "https://test.com/api/issue/1")

    assert len(sent) == 1
    assert exc_info.value.retry_after == pytest.approx(3600, abs=5)
    assert limiter._in_flight == 0


def test_rate_limiter_notified_of_429_before_release(
    session: Session, monkeypatch, make_response
) -> None:
    """A 429 response reports its Retry-After to the limiter, then releases the slot."""
    calls = []

    class FakeLimiter:
        def acquire(self, status):
            calls.append(("acquire",))

        def on_rate_limited(self, retry_after):
            calls.append(("on_rate_limited", retry_after))

        def release(self, status):
            calls.append(("release",))

    session.rate_limiter = FakeLimiter()

    monkeypatch.setattr(
        session._http, "request", lambda *a, **k: make_response(429, headers={"Retry-After": "12"})
    )

    session._execute_http_request("GET", "https://test.com/api/issue/1")

    assert calls == [("acquire",), ("on_rate_limited", 12.0), ("release",)]


def test_rate_limiter_notified_of_429_without_retry_after(
    session: Session, monkeypatch, make_response
) -> None:
    """A 429 with no Retry-After header reports 0 to the limiter."""
    reported = []

    class FakeLimiter:
        def acquire(self, status):
            pass

        def on_rate_limited(self, retry_after):
            reported.append(retry_after)

        def release(self, status):
            pass

    session.rate_limiter = FakeLimiter()

    monkeypatch.setattr(session._http, "request", lambda *a, **k: make_response(429))

    session._execute_http_request("GET", "https://test.com/api/issue/1")

    assert reported == [0.0]


def test_rate_limiter_not_notified_of_successful_response(
    session: Session, monkeypatch, make_response
) -> None:
    """Non-429 responses never trigger the on_rate_limited hook."""
    reported = []

    class FakeLimiter:
        def acquire(self, status):
            pass

        def on_rate_limited(self, retry_after):
            reported.append(retry_after)

        def release(self, status):
            pass

    session.rate_limiter = FakeLimiter()

    monkeypatch.setattr(session._http, "request", lambda *a, **k: make_response())

    session._execute_http_request("GET", "https://test.com/api/issue/1")

    assert reported == []


def test_rate_limiter_missing_on_rate_limited_raises_rate_limiter_error(
    session: Session,
    monkeypatch,
    make_response,
) -> None:
    """A rate_limiter missing on_rate_limited() raises RateLimiterError on a 429, still releasing."""
    calls = []

    class NoHook:
        def acquire(self, status):
            pass

        def release(self, status):
            calls.append("release")

    session.rate_limiter = NoHook()  # pyright: ignore[reportAttributeAccessIssue]  (deliberately lacks on_rate_limited)

    monkeypatch.setattr(
        session._http, "request", lambda *a, **k: make_response(429, headers={"Retry-After": "1"})
    )

    with pytest.raises(exceptions.RateLimiterError):
        session._execute_http_request("GET", "https://test.com/api/issue/1")

    assert calls == ["release"]


def test_rate_limiter_internal_attribute_error_is_not_misreported(
    session: Session, monkeypatch
) -> None:
    """An AttributeError raised inside acquire() propagates as-is, not as RateLimiterError."""

    class Buggy:
        def on_rate_limited(self, retry_after):
            pass

        def acquire(self, status):
            msg = "missing"
            raise AttributeError(msg)

        def release(self, status):
            pass

    session.rate_limiter = Buggy()
    monkeypatch.setattr(session._http, "request", lambda *a, **k: MagicMock())

    with pytest.raises(AttributeError) as exc_info:
        session._request_data("GET", "https://test.com/api/issue/1")

    assert not isinstance(exc_info.value, exceptions.RateLimiterError)


def test_rate_limiter_release_failure_does_not_discard_response(
    session: Session, monkeypatch, caplog
) -> None:
    """An exception from release() is logged and the successful response still returned."""

    class FailingRelease:
        def on_rate_limited(self, retry_after):
            pass

        def acquire(self, status):
            pass

        def release(self, status):
            msg = "backing store unreachable"
            raise ConnectionError(msg)

    session.rate_limiter = FailingRelease()
    response = MagicMock(status_code=200, headers={})
    monkeypatch.setattr(session._http, "request", lambda *a, **k: response)

    with caplog.at_level(logging.ERROR, logger="mokkari.session"):
        result = session._execute_http_request("GET", "https://test.com/api/issue/1")

    assert result is response
    assert "release() failed" in caplog.text


def test_rate_limiter_on_rate_limited_failure_still_releases(
    session: Session, monkeypatch, caplog
) -> None:
    """An exception from on_rate_limited() is logged, and the slot is still released."""
    calls = []

    class FailingHook:
        def acquire(self, status):
            pass

        def on_rate_limited(self, retry_after):
            msg = "backing store unreachable"
            raise ConnectionError(msg)

        def release(self, status):
            calls.append("release")

    session.rate_limiter = FailingHook()
    response = MagicMock(status_code=429, headers={"Retry-After": "1"})
    monkeypatch.setattr(session._http, "request", lambda *a, **k: response)

    with caplog.at_level(logging.ERROR, logger="mokkari.session"):
        result = session._execute_http_request("GET", "https://test.com/api/issue/1")

    assert result is response
    assert calls == ["release"]
    assert "on_rate_limited() failed" in caplog.text


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
    assert result is not None
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

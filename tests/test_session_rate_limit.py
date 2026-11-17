"""Test Session's rate limiting.

Metron's sustained (daily) limit is dynamic per user (higher for OpenCollective donors), so
Session tracks rate limits reactively from the X-RateLimit-* response headers instead of a
fixed local quota. These tests cover that tracking, the fail-fast check, and dispatch to an
injected rate limiter.
"""

import datetime as dt
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest
from requests.exceptions import ConnectionError as ConnError, TooManyRedirects

from mokkari import exceptions, rate_limit
from mokkari.rate_limit import HeaderPacedRateLimiter
from mokkari.session import Session


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


def test_request_data_survives_malformed_rate_limit_headers(
    session: Session,
    monkeypatch,
    make_response,
) -> None:
    """Malformed rate-limit headers shouldn't discard a response that already arrived."""
    session._update_rate_limit_status({"X-RateLimit-Burst-Remaining": "5"})
    monkeypatch.setattr(
        session._http,
        "request",
        lambda *a, **k: make_response(
            json_body={"id": 1, "name": "Test"},
            headers={
                "X-RateLimit-Burst-Remaining": "",
                "X-RateLimit-Burst-Reset": "not-a-timestamp",
                "X-RateLimit-Sustained-Remaining": "4998",
            },
        ),
    )

    result = session._request_data("GET", "https://test.com/api/issue/1")

    assert result == {"id": 1, "name": "Test"}
    assert session.rate_limit_status.burst.remaining == 5
    assert session.rate_limit_status.sustained.remaining == 4998


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

    monkeypatch.setattr(session._http, "request", lambda *a, **k: make_response())

    def failing_update(headers):
        msg = "header processing failed"
        raise ValueError(msg)

    monkeypatch.setattr(session, "_update_rate_limit_status", failing_update)

    with pytest.raises(ValueError, match="header processing failed"):
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

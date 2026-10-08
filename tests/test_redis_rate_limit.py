"""Test Redis Rate Limit module.

This module contains tests for RedisRateLimiter, run against fakeredis, which
executes the limiter's Lua scripts. Two limiters on one FakeServer stand in for
two processes sharing an account.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import fakeredis
import pytest

from mokkari.exceptions import RateLimitError
from mokkari.rate_limit import RateLimitStatus, RateLimitWindow
from mokkari.redis_rate_limit import RedisRateLimiter
from mokkari.session import Session


class _BlockedError(Exception):
    """Raised by the patched sleep to stop acquire() at its first wait."""


@pytest.fixture
def server() -> fakeredis.FakeServer:
    """A fake Redis server shared by every limiter in a test."""
    return fakeredis.FakeServer()


@pytest.fixture
def waits(monkeypatch) -> list[float]:
    """Record the first wait acquire() would sleep for, then stop it."""
    recorded: list[float] = []

    def fake_sleep(seconds: float) -> None:
        recorded.append(seconds)
        raise _BlockedError

    monkeypatch.setattr("mokkari.redis_rate_limit.time.sleep", fake_sleep)
    return recorded


def _limiter(server: fakeredis.FakeServer, account: str = "user", **kwargs) -> RedisRateLimiter:
    return RedisRateLimiter(fakeredis.FakeRedis(server=server), account, **kwargs)


def _in(seconds: float | None) -> datetime.datetime | None:
    if seconds is None:
        return None
    return datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=seconds)


def _status(  # noqa: PLR0913
    *,
    burst_limit: int | None = None,
    daily_limit: int | None = None,
    daily_remaining: int | None = None,
    daily_reset_in: float | None = None,
    burst_remaining: int | None = None,
    burst_reset_in: float | None = None,
) -> RateLimitStatus:
    return RateLimitStatus(
        burst=RateLimitWindow(
            limit=burst_limit, remaining=burst_remaining, reset=_in(burst_reset_in)
        ),
        sustained=RateLimitWindow(
            limit=daily_limit, remaining=daily_remaining, reset=_in(daily_reset_in)
        ),
    )


def test_acquire_does_not_block_before_limit_is_known(server, waits) -> None:
    """With no burst limit observed yet, requests aren't paced."""
    limiter = _limiter(server)

    for _ in range(5):
        limiter.acquire(RateLimitStatus())

    assert waits == []


def test_sends_are_spaced_across_processes(server, waits) -> None:
    """A send by one limiter delays the next send by another on the same account."""
    first = _limiter(server)
    second = _limiter(server)

    first.acquire(_status(burst_limit=2))
    with pytest.raises(_BlockedError):
        second.acquire(RateLimitStatus())

    # Two sends per 60s window are spaced 30s apart.
    assert waits[0] == pytest.approx(30, abs=1)


def test_other_accounts_are_not_paced_together(server, waits) -> None:
    """Limiters for different accounts keep separate state."""
    first = _limiter(server, "alice")
    second = _limiter(server, "bob")

    first.acquire(_status(burst_limit=1))
    second.acquire(_status(burst_limit=1))

    assert waits == []


def test_full_burst_window_blocks_until_oldest_send_ages_out(server, waits) -> None:
    """Once the window holds ``limit`` sends, the wait is until the oldest ages out."""
    client = fakeredis.FakeRedis(server=server)
    limiter = RedisRateLimiter(client, "user")
    limiter.acquire(_status(burst_limit=1))
    # Drop the spacing marker so only the window itself is left to block.
    client.delete(limiter._last_send_key)

    with pytest.raises(_BlockedError):
        limiter.acquire(RateLimitStatus())

    assert waits[0] == pytest.approx(60, abs=1)


def test_acquire_waits_then_sends(server, monkeypatch) -> None:
    """acquire() sleeps for the wait the script reports, then reserves a slot."""
    limiter = _limiter(server, burst_period=0.05)
    slept: list[float] = []
    real_sleep = __import__("time").sleep

    def spy(seconds: float) -> None:
        slept.append(seconds)
        real_sleep(seconds)

    monkeypatch.setattr("mokkari.redis_rate_limit.time.sleep", spy)

    limiter.acquire(_status(burst_limit=1))
    limiter.acquire(RateLimitStatus())

    assert slept
    assert all(0 < s <= 0.05 for s in slept)


def test_on_rate_limited_blocks_every_process(server, waits) -> None:
    """A 429 seen by one limiter backs off another on the same account."""
    first = _limiter(server)
    second = _limiter(server)

    first.on_rate_limited(5)
    with pytest.raises(_BlockedError):
        second.acquire(RateLimitStatus())

    assert waits[0] == pytest.approx(5, abs=0.1)


def test_on_rate_limited_only_extends_the_backoff(server, waits) -> None:
    """A shorter Retry-After arriving later doesn't cut an existing backoff short."""
    limiter = _limiter(server)

    limiter.on_rate_limited(10)
    limiter.on_rate_limited(1)
    with pytest.raises(_BlockedError):
        limiter.acquire(RateLimitStatus())

    assert waits[0] == pytest.approx(10, abs=0.1)


def test_on_rate_limited_without_retry_after_waits_a_burst_period(server, waits) -> None:
    """A 429 with no Retry-After backs off for one burst period."""
    limiter = _limiter(server, burst_period=7)

    limiter.on_rate_limited(0)
    with pytest.raises(_BlockedError):
        limiter.acquire(RateLimitStatus())

    assert waits[0] == pytest.approx(7, abs=0.1)


def test_exhausted_burst_window_blocks_every_process_until_reset(server, waits) -> None:
    """A response reporting no burst requests left holds every process until its reset."""
    first = _limiter(server)
    second = _limiter(server)

    first.release(_status(burst_remaining=0, burst_reset_in=5))
    with pytest.raises(_BlockedError):
        second.acquire(RateLimitStatus())

    assert waits[0] == pytest.approx(5, abs=0.1)


@pytest.mark.parametrize(
    ("remaining", "reset_in"),
    [(1, 5), (0, -5), (0, None)],
    ids=["requests-left", "reset-passed", "no-reset"],
)
def test_burst_window_with_room_does_not_block(server, waits, remaining, reset_in) -> None:
    """Only an exhausted window with a reset still ahead holds sends back."""
    limiter = _limiter(server)

    limiter.release(_status(burst_remaining=remaining, burst_reset_in=reset_in))
    limiter.acquire(RateLimitStatus())

    assert waits == []


def test_exhausted_burst_window_only_extends_the_backoff(server, waits) -> None:
    """An earlier burst reset doesn't cut a longer 429 backoff short."""
    limiter = _limiter(server)

    limiter.on_rate_limited(10)
    limiter.release(_status(burst_remaining=0, burst_reset_in=2))
    with pytest.raises(_BlockedError):
        limiter.acquire(RateLimitStatus())

    assert waits[0] == pytest.approx(10, abs=0.1)


def test_exhausted_daily_window_raises_across_processes(server, waits) -> None:
    """An exhausted daily window raises for every limiter on the account, without waiting."""
    first = _limiter(server)
    second = _limiter(server)

    first.release(_status(daily_limit=5000, daily_remaining=0, daily_reset_in=3600))
    with pytest.raises(RateLimitError) as exc_info:
        second.acquire(RateLimitStatus())

    assert exc_info.value.retry_after == pytest.approx(3600, abs=1)
    assert "5,000" in str(exc_info.value)
    assert waits == []


def test_each_send_counts_against_the_daily_window(server) -> None:
    """Sends reduce the held daily estimate before their responses arrive."""
    limiter = _limiter(server)

    limiter.acquire(_status(daily_remaining=2, daily_reset_in=3600))
    limiter.acquire(RateLimitStatus())

    with pytest.raises(RateLimitError):
        limiter.acquire(RateLimitStatus())


def test_daily_estimate_is_only_tightened(server) -> None:
    """A late response reporting more remaining doesn't loosen the estimate."""
    client = fakeredis.FakeRedis(server=server)
    limiter = RedisRateLimiter(client, "user")

    limiter.release(_status(daily_remaining=5, daily_reset_in=3600))
    limiter.release(_status(daily_remaining=10, daily_reset_in=3600))

    assert int(client.hget(limiter._daily_key, "remaining")) == 5


def test_daily_estimate_ignores_a_window_that_has_reset(server) -> None:
    """A response whose reset time has already passed is ignored."""
    client = fakeredis.FakeRedis(server=server)
    limiter = RedisRateLimiter(client, "user")

    limiter.release(_status(daily_remaining=0, daily_reset_in=-5))

    assert not client.exists(limiter._daily_key)
    limiter.acquire(RateLimitStatus())


def test_daily_estimate_without_reset_does_not_raise(server) -> None:
    """With no known reset there's no wait to report, so requests still go out."""
    client = fakeredis.FakeRedis(server=server)
    limiter = RedisRateLimiter(client, "user")

    limiter.release(_status(daily_remaining=0))
    limiter.acquire(RateLimitStatus())

    assert client.pttl(limiter._daily_key) > 0


def test_every_key_expires(server) -> None:
    """No key outlives its window, so a crashed process can't leave the account blocked."""
    client = fakeredis.FakeRedis(server=server)
    limiter = RedisRateLimiter(client, "user")

    limiter.acquire(_status(burst_limit=20, daily_limit=5000, daily_remaining=10))
    limiter.on_rate_limited(1)

    keys = client.keys("mokkari:ratelimit:*")
    assert len(keys) == 5
    assert all(client.pttl(key) > 0 for key in keys)


def test_release_without_status_changes_nothing(server) -> None:
    """release(None) after a failed request writes nothing."""
    client = fakeredis.FakeRedis(server=server)
    limiter = RedisRateLimiter(client, "user")

    limiter.release(None)

    assert client.keys("*") == []


def test_session_reports_429_to_redis(server, dummy_api_token: str, monkeypatch) -> None:
    """Session drives the limiter end to end: a 429 sets the shared backoff."""
    client = fakeredis.FakeRedis(server=server)
    limiter = RedisRateLimiter(client, "user")
    session = Session(api_token=dummy_api_token, rate_limiter=limiter)
    response = MagicMock(status_code=429, headers={"Retry-After": "30"})
    monkeypatch.setattr(session._http, "request", lambda *_a, **_k: response)

    session._execute_http_request("GET", "https://test.com/api/issue/1", {}, {}, None, None)

    assert client.pttl(limiter._blocked_key) == pytest.approx(30_000, abs=1000)


def test_session_reports_exhausted_burst_window_to_redis(
    server, dummy_api_token: str, monkeypatch
) -> None:
    """Session passes Metron's burst headers through, so a spent window blocks sends."""
    client = fakeredis.FakeRedis(server=server)
    limiter = RedisRateLimiter(client, "user")
    session = Session(api_token=dummy_api_token, rate_limiter=limiter)
    reset = int(datetime.datetime.now(datetime.UTC).timestamp()) + 30
    headers = {
        "X-RateLimit-Burst-Limit": "60",
        "X-RateLimit-Burst-Remaining": "0",
        "X-RateLimit-Burst-Reset": str(reset),
    }
    response = MagicMock(status_code=200, headers=headers)
    monkeypatch.setattr(session._http, "request", lambda *_a, **_k: response)

    session._execute_http_request("GET", "https://test.com/api/issue/1", {}, {}, None, None)

    assert client.pttl(limiter._blocked_key) == pytest.approx(30_000, abs=1500)

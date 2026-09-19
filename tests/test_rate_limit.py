"""Test Rate Limit module.

This module contains tests for the RateLimiter protocol and
HeaderPacedRateLimiter reference implementation.
"""

from __future__ import annotations

import datetime
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from mokkari.rate_limit import (
    HeaderPacedRateLimiter,
    RateLimitStatus,
    RateLimitWindow,
    _SendLog,
    _WindowEstimate,
)


def test_window_estimate_tightens_on_lower_remaining() -> None:
    """A newly observed, lower remaining value replaces the held estimate."""
    now = datetime.datetime.now(datetime.timezone.utc)
    reset = now + datetime.timedelta(seconds=60)
    estimate = _WindowEstimate()

    estimate.tighten(10, reset, now)
    estimate.tighten(5, reset, now)

    assert estimate.remaining == 5
    assert estimate.reset == reset


def test_window_estimate_ignores_higher_remaining() -> None:
    """A stale response reporting a higher remaining value doesn't loosen the estimate."""
    now = datetime.datetime.now(datetime.timezone.utc)
    reset = now + datetime.timedelta(seconds=60)
    estimate = _WindowEstimate()

    estimate.tighten(5, reset, now)
    estimate.tighten(10, reset, now)

    assert estimate.remaining == 5


def test_window_estimate_clears_after_reset_passes() -> None:
    """Once the held reset time has passed, the stale estimate is dropped entirely."""
    now = datetime.datetime.now(datetime.timezone.utc)
    past_reset = now - datetime.timedelta(seconds=1)
    estimate = _WindowEstimate(remaining=0, reset=past_reset)

    estimate.tighten(None, None, now)

    assert estimate.remaining is None
    assert estimate.reset is None


def test_window_estimate_wait_seconds_zero_when_room_available() -> None:
    """No wait is needed when remaining exceeds in-flight requests."""
    now = datetime.datetime.now(datetime.timezone.utc)
    estimate = _WindowEstimate(remaining=5, reset=now + datetime.timedelta(seconds=60))

    assert estimate.wait_seconds(in_flight=2, now=now) == 0.0


def test_window_estimate_wait_seconds_positive_when_exhausted() -> None:
    """A wait is reported when in-flight requests would exhaust the window."""
    now = datetime.datetime.now(datetime.timezone.utc)
    reset = now + datetime.timedelta(seconds=30)
    estimate = _WindowEstimate(remaining=2, reset=reset)

    wait = estimate.wait_seconds(in_flight=2, now=now)

    assert wait == pytest.approx(30, abs=2)


def test_send_log_allows_sends_until_limit_reached() -> None:
    """Sends fit in the window until the limit is hit, then a wait is reported."""
    log = _SendLog(period=60)
    log.limit = 2

    assert log.wait_seconds(now=100.0) == 0.0
    log.record(100.0)
    assert log.wait_seconds(now=101.0) == 0.0
    log.record(101.0)

    # The oldest send frees its slot 60s after it was made.
    assert log.wait_seconds(now=102.0) == pytest.approx(58.0)


def test_send_log_frees_slots_individually() -> None:
    """Each send ages out on its own schedule rather than the window resetting at once."""
    log = _SendLog(period=60)
    log.limit = 2
    log.record(100.0)
    log.record(130.0)

    # At t=160 the first send has aged out but the second hasn't: one slot is free.
    assert log.wait_seconds(now=160.0) == 0.0
    log.record(160.0)
    assert log.wait_seconds(now=161.0) == pytest.approx(29.0)


def test_send_log_shrinking_limit_waits_for_enough_slots() -> None:
    """A limit that drops below the logged count waits for enough sends to age out."""
    log = _SendLog(period=60)
    log.limit = 3
    for t in (100.0, 110.0, 120.0):
        log.record(t)
    log.limit = 1

    # With a limit of 1 a send only fits once the log is empty, so wait for the newest to age out.
    assert log.wait_seconds(now=121.0) == pytest.approx(59.0)


def test_send_log_interval_spreads_period_across_limit() -> None:
    """The even spacing is the period divided by the limit, or 0 while the limit is unknown."""
    log = _SendLog(period=60)
    assert log.interval == 0.0

    log.limit = 20

    assert log.interval == pytest.approx(3.0)


def test_acquire_does_not_block_when_no_state_observed() -> None:
    """Nothing is known yet, so acquire returns immediately."""
    limiter = HeaderPacedRateLimiter()

    start = time.monotonic()
    limiter.acquire(RateLimitStatus())
    limiter.acquire(RateLimitStatus())
    elapsed = time.monotonic() - start

    assert elapsed < 0.05
    limiter.release(None)
    limiter.release(None)


def test_acquire_spreads_sends_across_the_burst_window() -> None:
    """Sends are spaced period / limit apart instead of going out back-to-back."""
    limiter = HeaderPacedRateLimiter(burst_period=0.4)
    status = RateLimitStatus(burst=RateLimitWindow(limit=4))

    times = []
    for _ in range(3):
        limiter.acquire(status)
        times.append(time.monotonic())
        limiter.release(status)

    assert times[1] - times[0] >= 0.09
    assert times[2] - times[1] >= 0.09


def test_acquire_follows_burst_limit_changes_between_calls() -> None:
    """A burst limit the server lowers mid-run widens the spacing on the next send."""
    limiter = HeaderPacedRateLimiter(burst_period=0.4)
    roomy = RateLimitStatus(burst=RateLimitWindow(limit=100))
    tight = RateLimitStatus(burst=RateLimitWindow(limit=4))

    limiter.acquire(roomy)
    limiter.release(roomy)
    start = time.monotonic()
    limiter.acquire(roomy)  # 100/0.4s spacing is only 4ms
    fast = time.monotonic() - start
    limiter.release(roomy)

    start = time.monotonic()
    limiter.acquire(tight)  # now 0.1s spacing
    slow = time.monotonic() - start

    assert fast < 0.05
    assert slow >= 0.09


def test_acquire_waits_for_send_log_when_limit_drops_below_logged_sends() -> None:
    """When the server lowers the limit, the log holds sends longer than spacing alone would."""
    limiter = HeaderPacedRateLimiter(burst_period=0.4)
    roomy = RateLimitStatus(burst=RateLimitWindow(limit=4))  # 0.1s spacing
    tight = RateLimitStatus(burst=RateLimitWindow(limit=2))  # 0.2s spacing

    for _ in range(3):
        limiter.acquire(roomy)
        limiter.release(roomy)
    start = time.monotonic()
    limiter.acquire(tight)
    elapsed = time.monotonic() - start

    # Spacing alone would allow the next send 0.2s after the third; with three sends
    # logged against a limit of 2, the second must also age out, 0.3s after the third.
    assert elapsed >= 0.27


def test_acquire_ignores_server_reset_time_for_burst_window() -> None:
    """A burst reset time on a drifted clock (far in the future) doesn't cause a long wait."""
    limiter = HeaderPacedRateLimiter()
    far_future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    status = RateLimitStatus(burst=RateLimitWindow(limit=5, remaining=0, reset=far_future))

    start = time.monotonic()
    limiter.acquire(status)
    elapsed = time.monotonic() - start

    assert elapsed < 0.05


def test_on_rate_limited_blocks_for_retry_after() -> None:
    """After a 429, acquire blocks for the server's Retry-After."""
    limiter = HeaderPacedRateLimiter()

    limiter.on_rate_limited(0.15)
    start = time.monotonic()
    limiter.acquire(RateLimitStatus())
    elapsed = time.monotonic() - start

    assert elapsed >= 0.13


def test_on_rate_limited_without_retry_after_backs_off_a_full_burst_window() -> None:
    """A 429 with no Retry-After falls back to waiting out a whole burst period."""
    limiter = HeaderPacedRateLimiter(burst_period=0.15)

    limiter.on_rate_limited(0)
    start = time.monotonic()
    limiter.acquire(RateLimitStatus())
    elapsed = time.monotonic() - start

    assert elapsed >= 0.13


def test_on_rate_limited_never_shortens_an_existing_backoff() -> None:
    """A shorter Retry-After arriving later doesn't cut short a longer backoff."""
    limiter = HeaderPacedRateLimiter()

    limiter.on_rate_limited(0.2)
    limiter.on_rate_limited(0.01)
    start = time.monotonic()
    limiter.acquire(RateLimitStatus())
    elapsed = time.monotonic() - start

    assert elapsed >= 0.18


def test_on_rate_limited_blocks_already_waiting_callers() -> None:
    """A caller already blocked in acquire is held up by a 429 reported meanwhile."""
    limiter = HeaderPacedRateLimiter(burst_period=0.1)
    status = RateLimitStatus(burst=RateLimitWindow(limit=1))
    limiter.acquire(status)
    limiter.release(status)

    def waiter() -> float:
        start = time.monotonic()
        limiter.acquire(status)
        return time.monotonic() - start

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(waiter)
        time.sleep(0.02)  # let the waiter block on the full window
        limiter.on_rate_limited(0.3)
        elapsed = future.result(timeout=2)

    assert elapsed >= 0.28


def test_acquire_blocks_until_sustained_reset_when_exhausted() -> None:
    """An exhausted sustained window blocks until its reported reset time, then proceeds."""
    limiter = HeaderPacedRateLimiter()
    now = datetime.datetime.now(datetime.timezone.utc)
    reset = now + datetime.timedelta(seconds=0.1)
    status = RateLimitStatus(sustained=RateLimitWindow(limit=1, remaining=0, reset=reset))

    start = time.monotonic()
    limiter.acquire(status)
    elapsed = time.monotonic() - start

    assert elapsed >= 0.08


def test_release_wakes_a_blocked_acquire() -> None:
    """A caller blocked on the sustained window proceeds as soon as a release frees a slot."""
    limiter = HeaderPacedRateLimiter()
    now = datetime.datetime.now(datetime.timezone.utc)
    reset = now + datetime.timedelta(seconds=5)
    status = RateLimitStatus(sustained=RateLimitWindow(limit=1, remaining=1, reset=reset))

    # First caller takes the only slot.
    limiter.acquire(status)

    results = []

    def waiter() -> None:
        limiter.acquire(status)
        results.append("acquired")

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(waiter)
        time.sleep(0.05)  # give the waiter a moment to block on the exhausted slot
        assert results == []

        limiter.release(status)
        future.result(timeout=2)

    assert results == ["acquired"]


def test_concurrent_acquire_never_exceeds_burst_limit_in_a_period() -> None:
    """Concurrent callers never log more sends in one period than the burst limit allows."""
    period = 0.3
    limiter = HeaderPacedRateLimiter(burst_period=period)
    status = RateLimitStatus(burst=RateLimitWindow(limit=3))
    sent: list[float] = []

    def worker(_: int) -> None:
        limiter.acquire(status)
        sent.append(time.monotonic())
        limiter.release(status)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(worker, range(10)))

    sent.sort()
    for i, t in enumerate(sent):
        in_window = [x for x in sent if t <= x < t + period - 0.01]
        assert len(in_window) <= 3, (i, in_window)
    assert limiter._in_flight == 0

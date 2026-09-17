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


def test_acquire_does_not_block_when_no_state_observed() -> None:
    """Nothing is known yet, so acquire returns immediately."""
    limiter = HeaderPacedRateLimiter()

    limiter.acquire(RateLimitStatus())

    limiter.release(None)


def test_acquire_blocks_until_reset_when_exhausted() -> None:
    """Acquire blocks until the held window's reset time, then proceeds."""
    limiter = HeaderPacedRateLimiter()
    now = datetime.datetime.now(datetime.timezone.utc)
    reset = now + datetime.timedelta(seconds=0.1)
    status = RateLimitStatus(burst=RateLimitWindow(limit=1, remaining=0, reset=reset))

    start = time.monotonic()
    limiter.acquire(status)
    elapsed = time.monotonic() - start

    assert elapsed >= 0.08


def test_release_wakes_a_blocked_acquire() -> None:
    """A blocked acquire is released as soon as a concurrent release() frees a slot."""
    limiter = HeaderPacedRateLimiter()
    now = datetime.datetime.now(datetime.timezone.utc)
    reset = now + datetime.timedelta(seconds=5)
    status = RateLimitStatus(burst=RateLimitWindow(limit=1, remaining=1, reset=reset))

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


def test_concurrent_acquire_never_exceeds_configured_limit() -> None:
    """Concurrent callers never hold more in-flight slots than the burst limit allows."""
    limiter = HeaderPacedRateLimiter()
    now = datetime.datetime.now(datetime.timezone.utc)
    reset = now + datetime.timedelta(seconds=2)
    status = RateLimitStatus(burst=RateLimitWindow(limit=3, remaining=3, reset=reset))
    observed = []

    def worker(_: int) -> None:
        limiter.acquire(status)
        try:
            observed.append(limiter._in_flight)
        finally:
            limiter.release(status)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(worker, range(20)))

    assert max(observed) <= 3
    assert limiter._in_flight == 0

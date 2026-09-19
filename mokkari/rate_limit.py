"""Rate limiter module.

This module provides the following classes:

- RateLimitWindow: A single rate-limit window (burst or sustained) as last
  reported by Metron
- RateLimitStatus: The most recently observed rate-limit state for a ``Session``
- RateLimiter: Protocol for an injectable, opt-in pacing gate for ``Session``
- HeaderPacedRateLimiter: A ``RateLimiter`` that paces requests from the
  ``X-RateLimit-*`` headers Metron returns with every response
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from mokkari import exceptions

__all__ = ["HeaderPacedRateLimiter", "RateLimitStatus", "RateLimitWindow", "RateLimiter"]


@dataclass(frozen=True)
class RateLimitWindow:
    """A single rate-limit window (e.g. burst or sustained) as last reported by Metron.

    Attributes:
        limit: The maximum number of requests allowed in this window.
        remaining: The number of requests left in the current window.
        reset: When the window resets, as a UTC datetime.
    """

    limit: int | None = None
    remaining: int | None = None
    reset: datetime | None = None


@dataclass(frozen=True)
class RateLimitStatus:
    """The most recently observed rate-limit state for a Session.

    Populated from the ``X-RateLimit-*`` headers Metron sends with every
    response. All fields are ``None`` until the first request completes.

    Attributes:
        burst: The short-term (per-minute) window. Its limit is 20 at minimum and
            varies with server load.
        sustained: The daily window, whose limit varies by OpenCollective
            donor tier.
    """

    burst: RateLimitWindow = field(default_factory=RateLimitWindow)
    sustained: RateLimitWindow = field(default_factory=RateLimitWindow)


class RateLimiter(Protocol):
    """Protocol for an opt-in pacing gate injected into ``Session``.

    Pass an object implementing this protocol as ``Session(rate_limiter=...)``
    (or ``api(..., rate_limiter=...)``) to replace Session's default
    fail-fast rate-limit check with one that blocks until a request may be
    sent. Session dispatches to it from the single point where every HTTP
    request is sent, so it applies uniformly regardless of which public
    method triggered the call, and it is not shared between ``Session``
    instances: construct a separate rate limiter per ``Session``.
    """

    def acquire(self, status: RateLimitStatus) -> None:
        """Block, if necessary, until a request may be sent.

        Called once per HTTP send, immediately before it goes out. ``status``
        is the most recently observed ``RateLimitStatus`` for the owning
        ``Session`` (its fields may all be ``None`` on the very first call).
        Implementations that want to pace requests should block/sleep here
        and return only once a slot is available; an implementation may also
        choose to raise instead of blocking. Must be safe to call
        concurrently from multiple threads sharing one ``Session``.
        """
        ...

    def on_rate_limited(self, retry_after: float) -> None:
        """Record that Metron rejected a request with a 429 response.

        Called once per rejected request, after the response comes back and
        before ``release``. ``retry_after`` is the ``Retry-After`` value in
        seconds, which is relative to the moment the server sent it and so
        doesn't depend on the local clock matching the server's; it is ``0``
        when the response carried no ``Retry-After`` header. This is the hook
        for backing off after a rejection, since ``RateLimitStatus`` only
        describes window state and not why a request was refused.
        """
        ...

    def release(self, status: RateLimitStatus | None) -> None:
        """Record that a request begun by a prior ``acquire`` call has finished.

        Called exactly once for every successful ``acquire`` call, after the
        HTTP call returns, whether it succeeded, returned an error status, or
        failed to connect. ``status`` is the freshly updated
        ``RateLimitStatus`` reflecting that response's headers, or ``None``
        if the request failed before any headers were received (a connection
        error or timeout). This is the hook for decrementing an in-flight
        request count and reconciling a local remaining-capacity estimate.
        """
        ...


@dataclass
class _WindowEstimate:
    """A rate limiter's own held estimate of one window's remaining capacity.

    Used for the sustained (daily) window, which is too long to track with a
    local send log: it starts from the server's reported ``remaining`` and
    ``reset`` instead, so it does depend on the local clock roughly agreeing
    with Metron's.
    """

    remaining: int | None = None
    reset: datetime | None = None

    def tighten(self, remaining: int | None, reset: datetime | None, now: datetime) -> None:
        """Merge in a newly observed ``(remaining, reset)`` pair.

        The held estimate is only ever tightened, never loosened: a newly
        observed ``remaining`` only replaces the held value when it's lower,
        so a late response can't make the estimate look roomier than an
        already-observed, more exhausted state. Once the held reset time has
        passed, the window has rolled over server-side, so the stale
        estimate is dropped entirely rather than incorrectly tightened
        against it. A lower ``remaining`` observed without a ``reset`` keeps the
        reset already held rather than discarding it.
        """
        if self.reset is not None and self.reset <= now:
            self.remaining = None
            self.reset = None

        if remaining is None:
            return

        if self.remaining is None or remaining < self.remaining:
            self.remaining = remaining
            if reset is not None:
                self.reset = reset

    def wait_seconds(self, in_flight: int, now: datetime) -> float:
        """Seconds until this window has room for another request, or 0 if it already does.

        A window with no known reset time is never reported as exhausted, since
        there is no wait to report and holding it would block callers forever:
        nothing would be sent to refresh it. The request goes out and, if the
        window really is exhausted, Metron's 429 backs callers off through
        ``on_rate_limited`` instead. Metron sends ``Remaining`` and ``Reset``
        together, so this only arises if a proxy strips one of them.

        The result is a lower bound. Metron reports the reset as when the
        oldest request in the window ages out, which frees only one slot; if the
        window holds more requests than its limit allows (say the server lowered
        the limit), several must age out before a request fits.
        """
        if self.remaining is None or self.remaining - in_flight > 0 or self.reset is None:
            return 0.0
        return max(0.0, (self.reset - now).total_seconds())


class _SendLog:
    """A rolling log of this process's own send times, on the monotonic clock.

    Mirrors how Metron's throttle works: each request occupies a slot for one
    ``period`` and slots free individually as they age out, rather than the
    whole window resetting at once. Because it only ever compares local
    monotonic timestamps with each other, it is unaffected by the local
    wall clock drifting from the server's.
    """

    def __init__(self, period: float) -> None:
        self.period = period
        self.limit: int | None = None
        self._sent: deque[float] = deque()

    @property
    def interval(self) -> float:
        """Even spacing between sends that would just fill the window, or 0 if unknown."""
        if self.limit is None or self.limit < 1:
            return 0.0
        return self.period / self.limit

    def record(self, now: float) -> None:
        """Log a send at ``now``."""
        self._sent.append(now)

    def wait_seconds(self, now: float) -> float:
        """Seconds until a send fits in the window, or 0 if it already does."""
        if self.limit is None or self.limit < 1:
            return 0.0
        cutoff = now - self.period
        while self._sent and self._sent[0] <= cutoff:
            self._sent.popleft()
        if len(self._sent) < self.limit:
            return 0.0
        # The send that finally makes room is the (len - limit)th oldest to age out.
        return self._sent[len(self._sent) - self.limit] + self.period - now


class HeaderPacedRateLimiter:
    """A ``RateLimiter`` that paces requests using Metron's rate-limit headers.

    The burst (per-minute) window is paced from a monotonic log of this
    limiter's own send times, so it doesn't depend on the local clock
    matching Metron's, and sends are spaced evenly across the window
    (``burst_period / limit`` apart) rather than sent back-to-back until it's
    empty. The header-reported burst ``limit`` sizes the window and is
    re-read from every response, so it follows the server raising or lowering
    it with load. When Metron does reject a request with a 429, the
    ``Retry-After`` it sends (a relative number of seconds) blocks every
    caller for that long.

    The sustained (daily) window is too long to track with a local log, so
    it's held from the server-reported ``remaining`` and ``reset`` values,
    adjusted for requests that have been sent but haven't responded yet. A
    caller that would exceed it gets a ``RateLimitError`` instead of being
    blocked for what could be hours, with ``retry_after`` set to the time
    until the reported reset, so the application can decide whether to wait
    or quit. ``retry_after`` is a lower bound, not a guarantee. Metron reports
    the reset as when the oldest request in the window ages out, which frees
    a single slot, so when the window holds more requests than its limit
    allows (for example after the server lowers the daily limit below what
    the user has already used) the real wait is longer, and a caller who
    waits ``retry_after`` may be rejected again and should be ready to catch
    ``RateLimitError`` a second time. It also compares Metron's clock to the
    local one, so if the clocks disagree and a caller retries early, the
    resulting 429 backs everything off instead. Metron sends the daily
    window's headers on the 429 itself, so a rejection by the daily limit
    updates this estimate and the next ``acquire`` raises too. That 429 may
    carry no ``Retry-After``: in that same over-limit state DRF has no wait
    to report and omits it, which ``on_rate_limited`` sees as ``0``.

    This limiter only knows about requests it sent itself. Traffic from other
    processes sharing the account isn't visible to the burst window until
    Metron returns a 429.

    Construct one instance per ``Session``; don't share an instance across
    Sessions using different credentials.
    """

    def __init__(self, burst_period: float = 60.0) -> None:
        """Initialize a HeaderPacedRateLimiter with no observed state.

        Args:
            burst_period: Length in seconds of Metron's burst window.
        """
        self._condition = threading.Condition()
        self._burst = _SendLog(burst_period)
        self._sustained = _WindowEstimate()
        self._sustained_limit: int | None = None
        self._in_flight = 0
        self._last_send: float | None = None
        self._blocked_until = 0.0

    def acquire(self, status: RateLimitStatus) -> None:
        """Block until the burst window has room, then reserve a slot.

        Raises:
            RateLimitError: If the sustained (daily) window is exhausted. It
                is not waited out, since that could take hours.
        """
        with self._condition:
            self._observe(status)
            while True:
                now = time.monotonic()
                self._raise_if_daily_limit_reached()
                wait = max(
                    self._blocked_until - now,
                    self._burst.wait_seconds(now),
                    self._spacing_wait(now),
                )
                if wait <= 0:
                    self._burst.record(now)
                    self._last_send = now
                    self._in_flight += 1
                    return
                self._condition.wait(timeout=wait)

    def on_rate_limited(self, retry_after: float) -> None:
        """Block every caller for ``retry_after`` seconds, or a full burst window if unknown."""
        with self._condition:
            delay = retry_after if retry_after > 0 else self._burst.period
            self._blocked_until = max(self._blocked_until, time.monotonic() + delay)
            self._condition.notify_all()

    def release(self, status: RateLimitStatus | None) -> None:
        """Release the slot reserved by ``acquire`` and record fresher headers, if any."""
        with self._condition:
            self._in_flight = max(0, self._in_flight - 1)
            if status is not None:
                self._observe(status)
            self._condition.notify_all()

    def _raise_if_daily_limit_reached(self) -> None:
        """Raise ``RateLimitError`` rather than block until an exhausted daily window resets."""
        retry_after = self._sustained.wait_seconds(self._in_flight, datetime.now(timezone.utc))
        if retry_after <= 0:
            return
        # Imported here because mokkari.session imports this module.
        from mokkari.session import format_time  # noqa: PLC0415

        limit = self._sustained_limit
        limit_str = f"{limit:,}" if limit is not None else "your"
        msg = (
            f"Rate limit exceeded: You have reached the {limit_str} requests per day limit. "
            f"Please wait {format_time(retry_after)} before making another request."
        )
        raise exceptions.RateLimitError(msg, retry_after=retry_after)

    def _spacing_wait(self, now: float) -> float:
        """Seconds until the next evenly spaced send is due, or 0 if it already is."""
        if self._last_send is None:
            return 0.0
        return self._last_send + self._burst.interval - now

    def _observe(self, status: RateLimitStatus) -> None:
        if status.burst.limit is not None:
            self._burst.limit = status.burst.limit
        if status.sustained.limit is not None:
            self._sustained_limit = status.sustained.limit
        now = datetime.now(timezone.utc)
        self._sustained.tighten(status.sustained.remaining, status.sustained.reset, now)

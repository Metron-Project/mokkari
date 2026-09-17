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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

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
        burst: The short-term (per-minute) window, fixed for all users.
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
    """A rate limiter's own held estimate of one window's remaining capacity."""

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
        against it.
        """
        if self.reset is not None and self.reset <= now:
            self.remaining = None
            self.reset = None

        if remaining is None:
            return

        if self.remaining is None or remaining < self.remaining:
            self.remaining = remaining
            self.reset = reset

    def wait_seconds(self, in_flight: int, now: datetime) -> float:
        """Seconds until this window has room for another request, or 0 if it already does."""
        if self.remaining is None or self.remaining - in_flight > 0 or self.reset is None:
            return 0.0
        return max(0.0, (self.reset - now).total_seconds())


class HeaderPacedRateLimiter:
    """A ``RateLimiter`` that paces requests from Metron's rate-limit headers.

    Holds its own estimate of remaining burst/sustained capacity, tightened
    (never loosened) from every ``acquire``/``release`` call across every
    thread sharing the owning ``Session``, and adjusted for requests that
    have been sent but whose response hasn't come back yet. A caller that
    would exceed either window blocks until capacity frees, rather than
    raising immediately.

    Construct one instance per ``Session``; don't share an instance across
    Sessions using different credentials.
    """

    def __init__(self) -> None:
        """Initialize a HeaderPacedRateLimiter with no observed state."""
        self._condition = threading.Condition()
        self._burst = _WindowEstimate()
        self._sustained = _WindowEstimate()
        self._in_flight = 0

    def acquire(self, status: RateLimitStatus) -> None:
        """Block until neither window is exhausted, then reserve a slot."""
        with self._condition:
            self._tighten(status)
            while True:
                now = datetime.now(timezone.utc)
                wait = max(
                    self._burst.wait_seconds(self._in_flight, now),
                    self._sustained.wait_seconds(self._in_flight, now),
                )
                if wait <= 0:
                    self._in_flight += 1
                    return
                self._condition.wait(timeout=wait)

    def release(self, status: RateLimitStatus | None) -> None:
        """Release the slot reserved by ``acquire`` and record fresher headers, if any."""
        with self._condition:
            self._in_flight = max(0, self._in_flight - 1)
            if status is not None:
                self._tighten(status)
            self._condition.notify_all()

    def _tighten(self, status: RateLimitStatus) -> None:
        now = datetime.now(timezone.utc)
        self._burst.tighten(status.burst.remaining, status.burst.reset, now)
        self._sustained.tighten(status.sustained.remaining, status.sustained.reset, now)

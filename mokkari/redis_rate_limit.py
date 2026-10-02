"""Redis rate limiter module.

This module provides the following classes:

- RedisRateLimiter: A ``RateLimiter`` that keeps its pacing state in Redis, so
  every process and host using the same Metron account shares one view of it

It requires a Redis client, installed with the ``redis`` extra
(``pip install mokkari[redis]``). The client is passed in rather than created
here, so this module never imports ``redis`` at runtime.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Final
from uuid import uuid4

from mokkari.rate_limit import DEFAULT_BURST_PERIOD, RateLimitStatus, daily_limit_error

if TYPE_CHECKING:
    from datetime import datetime

    from redis import Redis

__all__ = ["RedisRateLimiter"]

# How long a burst limit, or a daily estimate that came without a reset time, is kept.
_STATE_TTL_MS: Final[int] = 24 * 60 * 60 * 1000

# Every script reads Redis's own clock rather than the caller's, so hosts sharing an
# account don't need their clocks in sync with each other.
_NOW = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
"""

# KEYS: send log (sorted set), last send, blocked until, daily estimate (hash), burst limit
# ARGV: burst period in ms, a member suffix unique to this call
# Returns {0, 0} once a slot is reserved, {0, ms} to wait for the burst window, or
# {1, ms, daily limit} when the daily window is exhausted for another ms.
_ACQUIRE: Final[str] = (
    _NOW
    + """
local period = tonumber(ARGV[1])

local remaining = tonumber(redis.call('HGET', KEYS[4], 'remaining'))
local reset = tonumber(redis.call('HGET', KEYS[4], 'reset'))
if remaining and reset and remaining <= 0 and reset > now then
  return {1, reset - now, redis.call('HGET', KEYS[4], 'limit') or ''}
end

local blocked = tonumber(redis.call('GET', KEYS[3]))
if blocked and blocked > now then
  return {0, blocked - now}
end

local limit = tonumber(redis.call('GET', KEYS[5]))
if limit and limit >= 1 then
  redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - period)
  local count = redis.call('ZCARD', KEYS[1])
  if count >= limit then
    -- The send that finally makes room is the (count - limit)th oldest to age out.
    local entry = redis.call('ZRANGE', KEYS[1], count - limit, count - limit, 'WITHSCORES')
    return {0, tonumber(entry[2]) + period - now}
  end
  local last = tonumber(redis.call('GET', KEYS[2]))
  local interval = math.floor(period / limit)
  if last and last + interval > now then
    return {0, last + interval - now}
  end
end

redis.call('ZADD', KEYS[1], now, now .. ':' .. ARGV[2])
redis.call('PEXPIRE', KEYS[1], period)
redis.call('SET', KEYS[2], now, 'PX', period)
if remaining then
  redis.call('HINCRBY', KEYS[4], 'remaining', -1)
end
return {0, 0}
"""
)

# KEYS: daily estimate (hash), burst limit, blocked until
# ARGV: burst limit, daily limit, daily remaining, daily reset in epoch ms ('' if unknown),
#       TTL in ms for state that has no reset of its own, burst remaining,
#       burst reset in epoch ms
_OBSERVE: Final[str] = (
    _NOW
    + """
if ARGV[1] ~= '' then
  redis.call('SET', KEYS[2], ARGV[1], 'PX', ARGV[5])
end

-- Metron counts its burst window from when requests arrive, so a send the local log
-- says is due can still land a moment early. An exhausted window blocks until the
-- reported reset instead, which only ever extends a backoff already held.
local burst_remaining = tonumber(ARGV[6])
local burst_reset = tonumber(ARGV[7])
if burst_remaining and burst_remaining <= 0 and burst_reset and burst_reset > now then
  local held = tonumber(redis.call('GET', KEYS[3]))
  if not held or burst_reset > held then
    redis.call('SET', KEYS[3], burst_reset, 'PX', burst_reset - now)
  end
end

local reset = tonumber(ARGV[4])
-- A response whose window has already reset describes a window that no longer exists.
local stale = reset and reset <= now
local remaining = tonumber(ARGV[3])
if remaining and not stale then
  local held = tonumber(redis.call('HGET', KEYS[1], 'remaining'))
  if not held or remaining < held then
    redis.call('HSET', KEYS[1], 'remaining', remaining)
    if reset then
      redis.call('HSET', KEYS[1], 'reset', reset)
      -- The estimate expires with the window, so a rolled-over window is never held.
      redis.call('PEXPIREAT', KEYS[1], reset)
    end
  end
end

if redis.call('EXISTS', KEYS[1]) == 1 then
  if ARGV[2] ~= '' then
    redis.call('HSET', KEYS[1], 'limit', ARGV[2])
  end
  if redis.call('PTTL', KEYS[1]) == -1 then
    redis.call('PEXPIRE', KEYS[1], ARGV[5])
  end
end
return 0
"""
)

# KEYS: blocked until
# ARGV: delay in ms
_BACKOFF: Final[str] = (
    _NOW
    + """
local deadline = now + tonumber(ARGV[1])
local held = tonumber(redis.call('GET', KEYS[1]))
if not held or deadline > held then
  redis.call('SET', KEYS[1], deadline, 'PX', ARGV[1])
end
return 0
"""
)


def _arg(value: int | None) -> int | str:
    """Encode an optional script argument, with ``''`` standing in for unknown."""
    return "" if value is None else value


def _epoch_ms(moment: datetime | None) -> int | None:
    """Convert an optional reset time to epoch milliseconds."""
    return None if moment is None else round(moment.timestamp() * 1000)


class RedisRateLimiter:
    """A ``RateLimiter`` that keeps its pacing state in Redis.

    It paces requests the same way as ``HeaderPacedRateLimiter``, but the state
    lives in Redis under keys named for ``account``, so every process and host
    that uses the same account shares one burst window, one daily estimate and
    one 429 backoff. ``HeaderPacedRateLimiter`` only sees its own requests, so
    several workers on one account can overrun the burst window together; with
    this limiter they are paced as one.

    - The burst (per-minute) window is a shared log of send times, and sends
      are spaced evenly across it (``burst_period / limit`` apart). The limit is
      re-read from every response's headers. When a response reports the burst
      window exhausted, every caller also waits for its reported reset, since
      Metron times its window from when requests arrive rather than when they
      were sent.
    - When Metron rejects a request with a 429, every caller sharing the account
      is blocked for the ``Retry-After`` it sent, or a full burst window if none.
    - The daily window is held from the server-reported ``remaining`` and
      ``reset`` values, only ever tightened, and reduced by one for every
      request sent. A caller that would exceed it gets a ``RateLimitError``
      with ``retry_after`` set to the time until the reported reset, rather
      than being blocked for what could be hours.

    Times are read from the Redis server's clock, so the burst window doesn't
    depend on the clocks of the hosts sharing it. The daily reset is still
    Metron's, so it depends on the Redis server's clock roughly agreeing with
    Metron's; if it doesn't and a caller retries early, the resulting 429 backs
    everyone off instead.

    Every key expires on its own, so a process that crashes mid-request leaves
    nothing behind that blocks the others. A request that was sent but whose
    response never arrived still counts against the daily estimate until the
    next response corrects it or the window resets.

    Construct one instance per ``Session``. Instances in any process that use
    the same ``client`` server, ``key_prefix`` and ``account`` share state.
    """

    def __init__(
        self,
        client: Redis,
        account: str,
        *,
        burst_period: float = DEFAULT_BURST_PERIOD,
        key_prefix: str = "mokkari:ratelimit",
    ) -> None:
        """Initialize a RedisRateLimiter.

        Args:
            client: A synchronous ``redis.Redis`` client (or compatible, such
                as a ``redis.RedisCluster``). It's used as-is and never closed.
            account: Identifies the Metron account whose limits are being
                shared, such as its username. Limiters that share an
                ``account`` share state, so use a distinct value per account.
                It appears in key names, so don't use the API token itself.
            burst_period: Length in seconds of Metron's burst window.
            key_prefix: Prefix for every key this limiter creates.
        """
        # The braces make a Redis Cluster hash tag, keeping one account's keys on
        # one node, which the scripts need since each touches several keys.
        base = f"{key_prefix}:{{{account}}}"
        self._send_log_key = f"{base}:burst:sends"
        self._last_send_key = f"{base}:burst:last"
        self._burst_limit_key = f"{base}:burst:limit"
        self._blocked_key = f"{base}:blocked_until"
        self._daily_key = f"{base}:daily"
        self._period_ms = max(1, round(burst_period * 1000))
        self._acquire_script = client.register_script(_ACQUIRE)
        self._observe_script = client.register_script(_OBSERVE)
        self._backoff_script = client.register_script(_BACKOFF)

    def acquire(self, status: RateLimitStatus) -> None:
        """Block until the shared burst window has room, then reserve a slot.

        Raises:
            RateLimitError: If the shared daily window is exhausted. It is not
                waited out, since that could take hours.
        """
        self._observe(status)
        keys = [
            self._send_log_key,
            self._last_send_key,
            self._blocked_key,
            self._daily_key,
            self._burst_limit_key,
        ]
        while True:
            code, wait_ms, *rest = self._acquire_script(
                keys=keys, args=[self._period_ms, uuid4().hex]
            )
            if code == 1:
                limit = int(rest[0]) if rest and rest[0] else None
                raise daily_limit_error(limit, wait_ms / 1000)
            if wait_ms <= 0:
                return
            # Other processes can't wake this one, so sleep exactly as long as the
            # script said; that's when the slot it was waiting on frees.
            time.sleep(wait_ms / 1000)

    def on_rate_limited(self, retry_after: float) -> None:
        """Block every caller on the account for ``retry_after`` seconds, or a burst window."""
        delay_ms = round(retry_after * 1000) if retry_after > 0 else self._period_ms
        self._backoff_script(keys=[self._blocked_key], args=[max(1, delay_ms)])

    def release(self, status: RateLimitStatus | None) -> None:
        """Record fresher headers, if any.

        The send log needs no release: each send frees its slot by ageing out.
        """
        if status is not None:
            self._observe(status)

    def _observe(self, status: RateLimitStatus) -> None:
        burst, sustained = status.burst, status.sustained
        if (
            burst.limit is None
            and burst.remaining is None
            and sustained.limit is None
            and sustained.remaining is None
        ):
            return
        self._observe_script(
            keys=[self._daily_key, self._burst_limit_key, self._blocked_key],
            args=[
                _arg(burst.limit),
                _arg(sustained.limit),
                _arg(sustained.remaining),
                _arg(_epoch_ms(sustained.reset)),
                _STATE_TTL_MS,
                _arg(burst.remaining),
                _arg(_epoch_ms(burst.reset)),
            ],
        )

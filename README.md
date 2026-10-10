# Mokkari

[![PyPI - Version](https://img.shields.io/pypi/v/mokkari.svg)](https://pypi.org/project/mokkari/)
[![PyPI - Python](https://img.shields.io/pypi/pyversions/mokkari.svg)](https://pypi.org/project/mokkari/)
[![Ruff](https://img.shields.io/badge/Linter-Ruff-informational)](https://github.com/charliermarsh/ruff)
[![Pre-Commit](https://img.shields.io/badge/Pre--Commit-Enabled-informational?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

A python wrapper for the [Metron Comic Book Database](https://metron.cloud) API.

## Installation

```bash
pip install mokkari
```

## Authentication

Authenticate with an API token, which you can generate from your metron.cloud
account page:

```python
import mokkari

m = mokkari.api(api_token="your-api-token")
```

Username/password (Basic Auth) was removed in v5.0. If you're upgrading from
4.x, replace `mokkari.api(username, password)` with a token as shown above.

## Example Usage

```python
import mokkari

# Your own config file to keep your credentials secret
from config import api_token

m = mokkari.api(api_token=api_token)

# Get all Marvel comics for the week of 2021-06-07
this_week = m.issues_list(
    {
        "store_date_range_after": "2021-06-07",
        "store_date_range_before": "2021-06-13",
        "publisher_name": "marvel",
    }
)

# Print the results
for i in this_week:
    print(f"{i.id} {i.issue_name}")

    # Retrieve the detail for an individual issue
    asm_68 = m.issue(31660)

# Print the issue Description
print(asm_68.desc)
```

## Rate Limiting

The API allows at least 20 requests per minute (the server may allow more when
load is low), plus a daily limit that starts at 5,000 requests and is raised for
[OpenCollective](https://opencollective.com/metron) donors (up to 25,000/day).
Because the daily limit varies per user, mokkari doesn't hardcode it — it reads
the `X-RateLimit-*` headers Metron returns with every response and pre-empts a
request once those headers show a window is exhausted, avoiding an HTTP call
that would fail anyway. When a rate limit is exceeded, a `RateLimitError` is
raised.

The most recently observed state is available via `session.rate_limit_status`:

```python
status = m.rate_limit_status
print(f"Sustained remaining: {status.sustained.remaining}/{status.sustained.limit}")
```

### Handling Rate Limits

The `RateLimitError` includes a `retry_after` attribute that tells you exactly
how many seconds to wait before making another request:

```python
import mokkari
from mokkari.exceptions import RateLimitError
import time

m = mokkari.api(api_token=api_token)

try:
    issue = m.issue(31660)
except RateLimitError as e:
    # Display user-friendly message
    print(f"Rate limited: {e}")

    # Programmatically wait for the exact time needed
    print(f"Waiting {e.retry_after} seconds...")
    time.sleep(e.retry_after)

    # Retry the request
    issue = m.issue(31660)
```

### Thread Safety

A `Session` can be shared across threads, but the rate-limit check above is
advisory rather than a hard gate: it only blocks once the last known response
headers show a window is exhausted, and that check isn't synchronized with
sending the request. Concurrent threads can therefore each pass the check and
send their requests before either response updates `rate_limit_status`, letting
a burst of threads momentarily exceed the per-minute limit (Metron's server-side
limit still applies and will reject the excess requests).

If you're calling a shared `Session` from multiple threads, cap your own
concurrency instead of relying on `Session` to do it for you, e.g. keep a
`ThreadPoolExecutor` at or below the burst limit:

```python
from concurrent.futures import ThreadPoolExecutor

m = mokkari.api(api_token=api_token)

# Keep worker count at or below the burst limit (20/min at minimum) to avoid
# racing past the local rate-limit check.
with ThreadPoolExecutor(max_workers=20) as executor:
    issues = list(executor.map(m.issue, issue_ids))
```

### Pacing (opt-in)

Passing `rate_limiter` closes the gap described above: instead of racing past an
advisory check, every HTTP send is dispatched through the rate limiter first,
which can block a caller until capacity actually frees rather than letting it
send anyway. `mokkari.rate_limit.HeaderPacedRateLimiter` is a ready-to-use
implementation. It sizes the per-minute window from the `X-RateLimit-*` headers
but paces it from its own monotonic log of send times, so a local clock that has
drifted from Metron's doesn't matter, and it spaces sends evenly across the
window (at the 20/min floor, one every 3 seconds). If Metron still answers with
a 429, it backs every caller off by the `Retry-After` value the server sent:

```python
from concurrent.futures import ThreadPoolExecutor

import mokkari
from mokkari.rate_limit import HeaderPacedRateLimiter

m = mokkari.api(api_token=api_token, rate_limiter=HeaderPacedRateLimiter())

with ThreadPoolExecutor(max_workers=20) as executor:
    issues = list(executor.map(m.issue, issue_ids))
```

The limiter only blocks for the per-minute window, whose waits are seconds long.
When the daily limit is exhausted it raises `RateLimitError` instead of blocking
for what could be hours, with `retry_after` set to the time until the daily
window resets. That leaves it to your application to tell the user and either
wait or quit:

```python
import time

from mokkari.exceptions import RateLimitError
from mokkari.utils import format_time

try:
    issue = m.issue(31660)
except RateLimitError as e:
    if input(f"Daily limit reached. Wait {format_time(e.retry_after)}? (y/n): ") == "y":
        time.sleep(e.retry_after)
        issue = m.issue(31660)
```

Paginated list calls follow the same rules: if a page is rejected with a 429
they retry it through the limiter, which blocks until it's safe to send, and an
exhausted daily limit raises `RateLimitError` from the list call rather than
being waited out.

A rate limiter object is scoped to the `Session` it's passed to — construct one
per `Session` rather than sharing an instance across sessions using different
credentials. Passing your own object works too, as long as it implements the
`acquire`/`on_rate_limited`/`release` methods described in
[`mokkari.rate_limit.RateLimiter`](https://mokkari.readthedocs.io/en/stable/mokkari/rate_limit/).
Leaving `rate_limiter` unset (the default) keeps the raise-immediately behavior
described above.

### Pacing across processes with Redis

`HeaderPacedRateLimiter` only sees the requests its own process sends, so
several workers using one account can overrun the per-minute window together
until Metron answers with 429s. `mokkari.redis_rate_limit.RedisRateLimiter`
paces the same way but keeps its state in Redis, so every process and host using
the same `account` shares one per-minute window, one daily estimate and one 429
backoff. Install the `redis` extra and pass it a client:

```bash
pip install mokkari[redis]
```

```python
import redis

import mokkari
from mokkari.redis_rate_limit import RedisRateLimiter

client = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1, socket_timeout=1)
# Any stable name for your Metron account, such as its username. Don't use the
# token itself: it becomes part of key names anyone with Redis access can read.
m = mokkari.api(
    api_token=api_token,
    rate_limiter=RedisRateLimiter(client, account="your-username"),
)
```

It raises `RateLimitError` on an exhausted daily limit just like
`HeaderPacedRateLimiter`. Times come from the Redis server's clock, and every
key expires on its own, so a worker that crashes mid-request can't leave the
account blocked. If Redis is unreachable, `acquire` raises the client's
connection error and the request isn't sent. Set `socket_connect_timeout` and
`socket_timeout` on the client as above: without them, a Redis host that stops
responding, rather than refusing the connection, makes `acquire` wait on it
indefinitely. The limiter's own waits happen in the client, not in Redis, so a
short timeout doesn't cut them off.

## Caching

Pass a cache to keep responses locally, so repeated requests don't count against
your rate limit:

```python
import mokkari
from mokkari.sqlite_cache import SqliteCache

m = mokkari.api(api_token="your-token", cache=SqliteCache("mokkari_cache.db"))
```

`import mokkari` no longer loads `mokkari.sqlite_cache` in v5.0. If you're
upgrading from 4.x and refer to `mokkari.sqlite_cache.SqliteCache` after only
`import mokkari`, import the module explicitly as shown above.

### Sharing a cache with Redis

`SqliteCache` keeps its cache on one machine. `mokkari.redis_cache.RedisCache`
keeps it in Redis instead, so several processes or hosts can share it. It takes
the same `default_ttl`, `ttl` and `empty_list_ttl` options. Install the `redis`
extra and pass it a client:

```python
import redis

import mokkari
from mokkari.redis_cache import RedisCache

client = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1, socket_timeout=1)
m = mokkari.api(api_token="your-token", cache=RedisCache(client))
```

Entries expire through Redis's own TTLs, and every key starts with `key_prefix`
(`"mokkari:cache"` by default), so `clear()` leaves other data in the database
alone. It needs Redis 7.0 or later on a single server, not a Redis Cluster.
Writes find the entries to drop through per-resource index keys, so if Redis
evicts keys under memory pressure, an evicted index can leave stale entries
until they expire; size Redis so that eviction doesn't happen. If Redis is
unreachable, the request goes to Metron instead and the error is logged. Set
`socket_connect_timeout` and `socket_timeout` on the client as above: without
them, a Redis host that stops responding, rather than refusing the connection,
makes every request wait on it indefinitely.

## Connection Reuse

A `Session` keeps its connections to Metron open between requests, so repeated
calls don't pay a new TCP/TLS handshake each time. Cookies are never stored or
sent back. To release the connections deterministically, use the session as a
context manager or call `close()`:

```python
with mokkari.api(api_token="your-token") as m:
    issue = m.issue(1)
```

Closing is optional, and a closed session can still be used; it just opens new
connections. If the server drops an idle connection, the underlying HTTP library
notices and discards it when the next request checks it out, so a request opens
a fresh connection instead. The only failure is a race: if the server closes a
connection in the instant it is reused, that request raises an `ApiError`. This
is rare, and mokkari doesn't retry it automatically. Don't share a `Session`
across forked processes; create one per process.

## Documentation

[Read the project documentation](https://mokkari.readthedocs.io/en/stable/?badge=latest)

## Bugs/Requests

Please use the
[GitHub issue tracker](https://github.com/Metron-Project/mokkari/issues) to
submit bugs or request features.

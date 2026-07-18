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

## Example Usage

```python
import mokkari

# Your own config file to keep your credentials secret
from config import username, password

m = mokkari.api(username, password)

# Get all Marvel comics for the week of 2021-06-07
this_week = m.issues_list({"store_date_range_after": "2021-06-07", "store_date_range_before": "2021-06-13", "publisher_name": "marvel"})

# Print the results
for i in this_week:
    print(f"{i.id} {i.issue_name}")

# Retrieve the detail for an individual issue
    asm_68 = m.issue(31660)

# Print the issue Description
print(asm_68.desc)
```

## Rate Limiting

The API has a fixed limit of 20 requests per minute, plus a daily limit that
starts at 5,000 requests and is raised for
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

m = mokkari.api(username, password)

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

m = mokkari.api(username, password)

# Keep worker count at or below the burst limit (20/min) to avoid racing
# past the local rate-limit check.
with ThreadPoolExecutor(max_workers=20) as executor:
    issues = list(executor.map(m.issue, issue_ids))
```

## Documentation

[Read the project documentation](https://mokkari.readthedocs.io/en/stable/?badge=latest)

## Bugs/Requests

Please use the
[GitHub issue tracker](https://github.com/Metron-Project/mokkari/issues) to
submit bugs or request features.

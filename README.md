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

The API has rate limits of 30 requests per minute and 10,000 requests per day.
Mokkari automatically enforces these limits locally to prevent unnecessary API
calls. When a rate limit is exceeded, a `RateLimitError` is raised.

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

## Documentation

[Read the project documentation](https://mokkari.readthedocs.io/en/stable/?badge=latest)

## Bugs/Requests

Please use the
[GitHub issue tracker](https://github.com/Metron-Project/mokkari/issues) to
submit bugs or request features.

# Changelog

All notable changes to mokkari are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `DEFAULT_BURST_PERIOD`, `DEFAULT_BURST_SLACK` and `burst_window()` are
  exported from `mokkari.rate_limit`.
- `HeaderPacedRateLimiter` and `RedisRateLimiter` take a `slack` argument: extra
  seconds each send is held in the burst window beyond `burst_period` (#199).

### Changed

- `HeaderPacedRateLimiter` and `RedisRateLimiter` hold each send for 2 seconds
  beyond Metron's 60-second burst window by default, since Metron times a
  request from when it arrives rather than when it was sent. A 20-per-minute
  limit is now paced at about 19.4 per minute. A custom `burst_period` gets no
  slack unless `slack` is passed (#199).
- `HeaderPacedRateLimiter` now also waits for the reported burst reset when a
  response shows the burst window exhausted, as `RedisRateLimiter` already did.
  This compares Metron's reset time with the local clock, so the wait is capped
  at one burst window (#199).
- `HeaderPacedRateLimiter` and `RedisRateLimiter` raise `ValueError` at
  construction for a `burst_period` that isn't a positive finite number, or a
  `slack` that isn't a non-negative finite number. In 5.0.0, `burst_period=0`
  quietly turned off burst pacing (#199).

### Fixed

- `HeaderPacedRateLimiter` no longer draws about one 429 per burst window under
  sustained load (#198).
- `RedisRateLimiter` processes configured with different burst windows no longer
  trim or expire sends that another process sharing the account still holds
  (#199).

## [5.0.0] - 2026-10-24

### Changed

- Schemas synced with the latest Metron API (#193).
- `SqliteCache` sets how long entries are kept per resource, with `default_ttl`,
  a `ttl` map, and `empty_list_ttl`, rather than one expiry for everything. A
  TTL can be a `timedelta`, `SqliteCache.NEVER` or `SqliteCache.NO_CACHE`.
  `collection`, `pull_list` and `wish_list` aren't cached unless added to `ttl`
  (#184).
- An existing 4.x cache database is emptied the first time 5.0 opens it (#184).
- `mokkari.sqlite_cache` is no longer loaded by `import mokkari` (#184).
- The string schema enums are now `StrEnum`s (#175).
- A PATCH or POST invalidates only the cache entries it can change (#190).
  `SqliteCache.invalidate()` and `SqliteCache.clear()` remove entries by hand.

### Removed

- Basic auth support. Use `mokkari.api(api_token=...)` (#174).
- The backwards-compatibility re-exports from `mokkari.session` (#178).
- `SqliteCache.con` (#196).

### Fixed

- A netrc entry no longer replaces the Bearer token (#176).
- Cache contention is logged less noisily (#196).

## [4.10.0] - 2026-10-11

### Deprecated

- Importing the moved names from `mokkari.session` (#179).
- Basic auth, ahead of its removal in 5.0 (#177).
- `SqliteCache`'s `expire` and 4.x-style custom caches (#188).

### Fixed

- A netrc entry no longer replaces the Bearer token (#176).

## [4.9.0] - 2026-10-02

### Added

- `RedisRateLimiter`, which keeps its pacing state in Redis so every process and
  host using the same Metron account shares one burst window, daily estimate and
  429 backoff. Install with the `redis` extra (#170).
- Python 3.15 support (#172).

### Removed

- Python 3.10 support (#172).

## [4.8.0] - 2026-09-21

### Added

- An opt-in `rate_limiter` for `Session` and `mokkari.api()`, which blocks each
  request until there is capacity instead of the default advisory check.
  `HeaderPacedRateLimiter` is the ready-made implementation, and the
  `RateLimiter` protocol allows custom ones (#167).
- `Session` can be used as a context manager and has a `close()` method (#169).

### Changed

- `Session` reuses one pooled `requests.Session` (up to 32 connections) rather
  than opening a connection per request. Cookies are never stored or sent back
  (#169).
- Without a `rate_limiter`, pagination sleeps exactly the server's
  `Retry-After`, without adding 2 seconds (#168).

### Fixed

- Paginated list calls no longer retry a 429 forever. They raise
  `RateLimitError` after 3 consecutive 429s without `Retry-After`, or 20 on the
  same page with it (#168).
- With a `rate_limiter`, pagination no longer sleeps on top of the limiter's own
  wait, and a `RateLimitError` the limiter raises reaches the caller (#168).
- Some request errors, such as too many redirects, no longer leak a rate-limiter
  slot (#167).

## [4.7.1] - 2026-09-14

### Removed

- The stale `issue_count` field from `PullListSeriesDetail` (#162).

## [4.7.0] - 2026-09-06

### Changed

- Series and pull list schemas synced with the Metron API (#159).

## [4.6.0] - 2026-08-20

### Added

- `Session.last_cache_status`, which reports Metron's `X-Cache` header for the
  last response (#158).

## [4.5.0] - 2026-08-15

### Added

- Italian comics support in the Publisher, Series and Issue schemas (#157).
- `collection_add()` and `collection_delete()` (#155).

## [4.4.0] - 2026-07-28

### Added

- Token-based API authentication with `mokkari.api(api_token=...)` (#154).

## [4.3.0] - 2026-07-25

### Added

- `alt_names` field on the Series and IssueSeries schemas (#152).

## [4.2.0] - 2026-07-21

### Added

- `average_rating` and `rating_count` fields on the Issue schema (#151).

## [4.1.0] - 2026-07-20

### Added

- Previous and next reading order links on `ReadingListRead` (#150).

## [4.0.1] - 2026-07-18

### Fixed

- `SqliteCache` is safe to share across threads (#148).

## [4.0.0] - 2026-07-16

### Changed

- Rate limiting tracks Metron's `X-RateLimit-*` response headers instead of a
  local `pyrate_limiter` bucket. `mokkari.api()` no longer takes a `bucket`
  argument (#146).

## Earlier releases

See the [GitHub releases](https://github.com/Metron-Project/mokkari/releases)
for versions before 4.0.0.

[Unreleased]: https://github.com/Metron-Project/mokkari/compare/v5.0.0...HEAD
[5.0.0]: https://github.com/Metron-Project/mokkari/compare/v4.9.0...v5.0.0
[4.10.0]: https://github.com/Metron-Project/mokkari/compare/v4.9.0...v4.10.0
[4.9.0]: https://github.com/Metron-Project/mokkari/compare/v4.8.0...v4.9.0
[4.8.0]: https://github.com/Metron-Project/mokkari/compare/v4.7.1...v4.8.0
[4.7.1]: https://github.com/Metron-Project/mokkari/compare/v4.7.0...v4.7.1
[4.7.0]: https://github.com/Metron-Project/mokkari/compare/v4.6.0...v4.7.0
[4.6.0]: https://github.com/Metron-Project/mokkari/compare/v4.5.0...v4.6.0
[4.5.0]: https://github.com/Metron-Project/mokkari/compare/v4.4.0...v4.5.0
[4.4.0]: https://github.com/Metron-Project/mokkari/compare/v4.3.0...v4.4.0
[4.3.0]: https://github.com/Metron-Project/mokkari/compare/v4.2.0...v4.3.0
[4.2.0]: https://github.com/Metron-Project/mokkari/compare/v4.1.0...v4.2.0
[4.1.0]: https://github.com/Metron-Project/mokkari/compare/v4.0.1...v4.1.0
[4.0.1]: https://github.com/Metron-Project/mokkari/compare/v4.0.0...v4.0.1
[4.0.0]: https://github.com/Metron-Project/mokkari/compare/v3.29.1...v4.0.0

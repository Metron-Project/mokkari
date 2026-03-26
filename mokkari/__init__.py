"""Project entry file."""

__all__ = ["__version__", "api"]

from importlib.metadata import version

# Keep this at beginning of file to prevent circular import with session
__version__ = version("mokkari")

from mokkari import exceptions, session, sqlite_cache


def api(  # noqa: PLR0913
    username: str | None = None,
    passwd: str | None = None,
    cache: sqlite_cache.SqliteCache | None = None,
    user_agent: str | None = None,
    dev_mode: bool = False,
    bucket: session.AbstractBucket | None = None,
) -> session.Session:
    """Entry function the sets login credentials for metron.cloud.

    Args:
        username: The username used for metron.cloud.
        passwd: The password used for metron.cloud.
        cache: SqliteCache to use.
        user_agent: The user agent string for the application using Mokkari.
            For example 'Foo Bar/1.0'.
        dev_mode: Whether the library should be run against a local Metron instance.
        bucket: Optional pyrate_limiter bucket for rate limiting. If not provided,
            a default SQLite-backed bucket is created and shared across sessions.
            Pass a custom bucket to share rate limit state across workers
            (e.g., using a Redis or database-backed bucket).

    Returns:
        A Session object.

    Raises:
        AuthenticationError: If Metron returns with an invalid API credentials response.

    Examples:
        Default SQLite-backed rate limiting (shared across sessions in the same process):

        >>> m = api("username", "password")

        Redis-backed rate limiting (shared across multiple workers or processes):

        >>> from pyrate_limiter import RedisBucket
        >>> import redis
        >>> pool = redis.ConnectionPool.from_url("redis://localhost:6379")
        >>> bucket = RedisBucket.init(mokkari.session.DEFAULT_RATES, redis.Redis(connection_pool=pool), "mokkari")
        >>> m = api("username", "password", bucket=bucket)

        In-memory bucket (useful for testing or single-process use without a database):

        >>> from pyrate_limiter import InMemoryBucket
        >>> m = api("username", "password", bucket=InMemoryBucket(mokkari.session.DEFAULT_RATES))

    """
    if username is None or passwd is None:
        raise exceptions.AuthenticationError

    return session.Session(
        username, passwd, cache=cache, user_agent=user_agent, dev_mode=dev_mode, bucket=bucket
    )

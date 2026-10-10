"""Project entry file."""

__all__ = ["__version__", "api"]

from importlib.metadata import version

# Keep this at beginning of file to prevent circular import with session
__version__ = version("mokkari")

from mokkari import rate_limit, session, sqlite_cache


def api(
    api_token: str,
    *,
    cache: sqlite_cache.Cache | None = None,
    user_agent: str | None = None,
    dev_mode: bool = False,
    rate_limiter: rate_limit.RateLimiter | None = None,
) -> session.Session:
    """Entry function the sets login credentials for metron.cloud.

    Args:
        api_token: An API token used for Bearer-token authentication, generated
            from your metron.cloud account page.
        cache: Response cache to use, such as a ``SqliteCache``.
        user_agent: The user agent string for the application using Mokkari.
            For example 'Foo Bar/1.0'.
        dev_mode: Whether the library should be run against a local Metron instance.
        rate_limiter: Optional pacing gate dispatched on every HTTP send, in
            place of the default fail-fast rate-limit check. Defaults to ``None``.

    Returns:
        A Session object.

    Raises:
        AuthenticationError: If the api_token is missing or empty.
        CacheError: If ``cache`` is missing a ``get`` or ``store`` method.

    Examples:
        >>> m = api("your-api-token")

    """
    return session.Session(
        api_token,
        cache=cache,
        user_agent=user_agent,
        dev_mode=dev_mode,
        rate_limiter=rate_limiter,
    )

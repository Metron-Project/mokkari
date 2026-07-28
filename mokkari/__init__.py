"""Project entry file."""

__all__ = ["__version__", "api"]

from importlib.metadata import version

# Keep this at beginning of file to prevent circular import with session
__version__ = version("mokkari")

from mokkari import session, sqlite_cache


def api(  # noqa: PLR0913, PLR0917
    username: str | None = None,
    passwd: str | None = None,
    cache: sqlite_cache.SqliteCache | None = None,
    user_agent: str | None = None,
    dev_mode: bool = False,
    api_token: str | None = None,
) -> session.Session:
    """Entry function the sets login credentials for metron.cloud.

    Args:
        username: The username used for metron.cloud.
        passwd: The password used for metron.cloud.
        cache: SqliteCache to use.
        user_agent: The user agent string for the application using Mokkari.
            For example 'Foo Bar/1.0'.
        dev_mode: Whether the library should be run against a local Metron instance.
        api_token: An API token used for Bearer-token authentication. Takes
            precedence over username/passwd when both are provided.

    Returns:
        A Session object.

    Raises:
        AuthenticationError: If neither an api_token nor a complete username/passwd
            pair is provided.

    Examples:
        >>> m = api("username", "password")
        >>> m = api(api_token="your-token-here")

    """
    return session.Session(
        username=username,
        passwd=passwd,
        cache=cache,
        user_agent=user_agent,
        dev_mode=dev_mode,
        api_token=api_token,
    )

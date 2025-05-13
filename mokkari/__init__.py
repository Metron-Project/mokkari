"""Project entry file."""

__all__ = ["__version__", "api"]

from importlib.metadata import version

# Keep this at beginning of file to prevent circular import with session
__version__ = version("mokkari")

from mokkari import exceptions, session, sqlite_cache


def api(
    username: str | None = None,
    passwd: str | None = None,
    cache: sqlite_cache.SqliteCache | None = None,
    user_agent: str | None = None,
    dev_mode: bool = False,
) -> session.Session:
    """Entry function the sets login credentials for metron.cloud.

    Args:
    ----
        username (str): The username used for metron.cloud.
        passwd (str): The password used for metron.cloud.
        cache (SqliteCache): SqliteCache to use
        user_agent (str): The user agent string for the application using Mokkari.
        For example 'Foo Bar/1.0'.
        dev_mode (bool): Whether the library should be run against a local Metron instance.

    Returns:
    -------
        A :obj:`Session` object

    Raises:
    ------
        AuthenticationError: If Metron returns with an invalid API credentials response.

    .. versionadded:: 2.5.0

        - Added ``user_agent`` argument.

    """
    if username is None or passwd is None:
        raise exceptions.AuthenticationError

    return session.Session(username, passwd, cache=cache, user_agent=user_agent, dev_mode=dev_mode)

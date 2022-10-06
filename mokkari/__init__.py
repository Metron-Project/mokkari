"""Project entry file."""

# Keep this at beginning of file to prevent circular import with session
__version__ = "2.3.2"

from typing import Optional

from mokkari import exceptions, session, sqlite_cache


def api(
    username: Optional[str] = None,
    passwd: Optional[str] = None,
    cache: sqlite_cache.SqliteCache = None,
) -> session.Session:
    """Entry function the sets login credentials for metron.cloud.

    Args:
        username (str): The username used for metron.cloud.
        passwd (str): The password used for metron.cloud.
        SqliteCache optional: SqliteCache to use

    Returns:
        A :obj:`Session` object

    Raises:
        AuthenticationError: If Metron returns with an invalid API credentials response.
    """
    if username is None:
        raise exceptions.AuthenticationError("Missing username.")

    if passwd is None:
        raise exceptions.AuthenticationError("Missing passwd.")

    return session.Session(username, passwd, cache=cache)

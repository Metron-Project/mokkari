"""Project entry file."""

# Keep this at beginning of file to prevent circular import with session
__version__ = "1.0.0"

from typing import Optional

from mokkari import exceptions, session, sqlite_cache


def api(
    username: Optional[str] = None,
    passwd: Optional[str] = None,
    cache: sqlite_cache.SqliteCache = None,
):
    """Entry function the sets login credentials for metron.cloud.

    :param str username: The username used for metron.cloud.
    :param str passwd: The password used for metron.cloud.
    :param SqliteCache optional: SqliteCache to use
    """
    if username is None:
        raise exceptions.AuthenticationError("Missing username.")

    if passwd is None:
        raise exceptions.AuthenticationError("Missing passwd.")

    return session.Session(username, passwd, cache=cache)

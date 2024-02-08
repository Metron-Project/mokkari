"""Project entry file."""

# Keep this at beginning of file to prevent circular import with session
__version__ = "3.0.1"


from mokkari import exceptions, session, sqlite_cache


def api(
    username: str | None = None,
    passwd: str | None = None,
    cache: sqlite_cache.SqliteCache = None,
    user_agent: str | None = None,
) -> session.Session:
    """Entry function the sets login credentials for metron.cloud.

    Args:
        username (str): The username used for metron.cloud.
        passwd (str): The password used for metron.cloud.
        cache (SqliteCache): SqliteCache to use
        user_agent (str): The user agent string for the application using Mokkari.
        For example 'Foo Bar/1.0'.

    Returns:
        A :obj:`Session` object

    Raises:
        AuthenticationError: If Metron returns with an invalid API credentials response.

    .. versionadded:: 2.5.0

        - Added ``user_agent`` argument.
    """
    if username is None:
        raise exceptions.AuthenticationError("Missing username.")

    if passwd is None:
        raise exceptions.AuthenticationError("Missing passwd.")

    return session.Session(username, passwd, cache=cache, user_agent=user_agent)

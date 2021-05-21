from . import exceptions, sesssion

# Projects version information used in setup.py
VERSION_INFO = (0, 0, 4)
VERSION = ".".join(str(c) for c in VERSION_INFO)


def api(username=None, passwd=None):
    """ Entry function the sets login credentials for metron.cloud.

    :param username: The username used for metron.cloud.
    :param passwd: The password used for metron.cloud.
    """
    if username is None:
        raise exceptions.AuthenticationError("Missing username.")

    if passwd is None:
        raise exceptions.AuthenticationError("Missing passwd.")

    return sesssion.Session(username, passwd)

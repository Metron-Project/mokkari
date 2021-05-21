from . import exceptions, sesssion

"""Projects version information used in setup.py"""
VERSION_INFO = (0, 0, 1)
VERSION = ".".join(str(c) for c in VERSION_INFO)


def api(username=None, passwd=None):
    if username is None:
        raise exceptions.AuthenticationError("Missing username.")

    if passwd is None:
        raise exceptions.AuthenticationError("Missing passwd.")

    return sesssion.Session(username, passwd)

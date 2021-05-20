from . import sesssion, exceptions

def api(username=None, passwd=None):
    if username is None:
        raise exceptions.AuthenticationError("Missing username.")

    if passwd is None:
        raise exceptions.AuthenticationError("Missing passwd.")

    return sesssion.Session(username, passwd)
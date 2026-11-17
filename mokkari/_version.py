"""The installed version of mokkari.

Kept in its own module so the modules ``mokkari/__init__.py`` imports can read it without
importing the package itself.
"""

__all__ = ["__version__"]

from importlib.metadata import version

__version__ = version("mokkari")

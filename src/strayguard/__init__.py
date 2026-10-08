"""strayguard: catch files that do not belong before you commit them."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("strayguard")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

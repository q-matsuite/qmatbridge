"""QMatBridge — materials databases to first-quantized Hamiltonians."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("qmatbridge")
except PackageNotFoundError:
    __version__ = "0.6.0"

__all__ = ["__version__"]

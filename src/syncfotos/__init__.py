"""Paquet principal de SyncFotos."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("syncfotos")
except PackageNotFoundError:
    __version__ = "desconeguda"

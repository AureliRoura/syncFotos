"""Paquet principal de SyncFotos."""

import subprocess
from importlib.metadata import PackageNotFoundError, distributions, version
from pathlib import Path

try:
    tags = subprocess.check_output(
        ["git", "tag", "--points-at", "HEAD", "--sort=-version:refname", "--list", "v[0-9]*"],
        cwd=Path(__file__).resolve().parents[2],
        stderr=subprocess.DEVNULL,
        text=True,
    ).splitlines()
except (OSError, subprocess.CalledProcessError):
    tags = []

if tags:
    __version__ = tags[0][1:]
else:
    try:
        __version__ = version("syncfotos")
    except PackageNotFoundError:
        source_path = str(Path(__file__).resolve().parents[1])
        source_distribution = next(
            (
                distribution
                for distribution in distributions(path=[source_path])
                if (distribution.metadata.get("Name") or "").lower() == "syncfotos"
            ),
            None,
        )
        __version__ = source_distribution.version if source_distribution else "desconeguda"

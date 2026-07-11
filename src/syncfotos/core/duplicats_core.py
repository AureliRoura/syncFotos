from __future__ import annotations

import json
import os
import platform
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff", ".tif"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v", ".3gp", ".flv", ".wmv", ".mts", ".m2ts", ".ts"}


def load_cache(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_duplicate_groups(cache_data, root_dir: Path):
    """
    Retorna una llista de tuples (checksum, [rel_path, rel_path, ...])
    per a cada grup de fotos/vídeos duplicats trobats a la cache.

    Només es consideren fitxers amb extensions d'imatge o vídeo, i
    només els que realment existeixen al disc en aquest moment.
    """
    fitxers = cache_data.get("fitxers", {})
    media_exts = IMAGE_EXTS | VIDEO_EXTS
    by_checksum = defaultdict(list)
    missing_count = 0

    for rel_path, info in fitxers.items():
        if Path(rel_path).suffix.lower() not in media_exts:
            continue
        checksum = info.get("checksum")
        if not checksum:
            continue
        if not (root_dir / rel_path).exists():
            missing_count += 1
            continue
        by_checksum[checksum].append(rel_path)

    groups = []
    for checksum, paths in by_checksum.items():
        if len(paths) >= 2:
            groups.append((checksum, sorted(paths)))
    return groups, missing_count


def open_with_default_app(path: Path):
    """Obre un fitxer amb l'aplicació per defecte del sistema."""
    system = platform.system()
    if system == "Windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def format_size(size_bytes):
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def format_mtime(mtime):
    try:
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d  %H:%M:%S")
    except Exception:
        return "Desconegut"

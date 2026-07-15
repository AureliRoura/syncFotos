from __future__ import annotations

import json
import platform
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import ctypes


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
        shell32 = ctypes.windll.shell32
        kernel32 = ctypes.windll.kernel32

        class SHELLEXECUTEINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("fMask", ctypes.c_ulong),
                ("hwnd", ctypes.c_void_p),
                ("lpVerb", ctypes.c_wchar_p),
                ("lpFile", ctypes.c_wchar_p),
                ("lpParameters", ctypes.c_wchar_p),
                ("lpDirectory", ctypes.c_wchar_p),
                ("nShow", ctypes.c_int),
                ("hInstApp", ctypes.c_void_p),
                ("lpIDList", ctypes.c_void_p),
                ("lpClass", ctypes.c_wchar_p),
                ("hkeyClass", ctypes.c_void_p),
                ("dwHotKey", ctypes.c_ulong),
                ("hIconOrMonitor", ctypes.c_void_p),
                ("hProcess", ctypes.c_void_p),
            ]

        info = SHELLEXECUTEINFO()
        info.cbSize = ctypes.sizeof(SHELLEXECUTEINFO)
        info.fMask = 0x00000040  # SEE_MASK_NOCLOSEPROCESS
        info.lpVerb = "open"
        info.lpFile = str(path)
        info.nShow = 1

        if not shell32.ShellExecuteExW(ctypes.byref(info)):
            raise OSError(f"No s'ha pogut obrir '{path}'")

        return info.hProcess
    elif system == "Darwin":
        return subprocess.Popen(["open", str(path)])
    else:
        return subprocess.Popen(["xdg-open", str(path)])


def stop_opened_app(handle):
    if handle is None:
        return

    if hasattr(handle, "poll"):
        try:
            if handle.poll() is None:
                handle.terminate()
                try:
                    handle.wait(timeout=1)
                except Exception:
                    handle.kill()
        except Exception:
            pass
        return

    if platform.system() == "Windows":
        kernel32 = ctypes.windll.kernel32
        try:
            kernel32.TerminateProcess(ctypes.c_void_p(handle), 0)
        except Exception:
            pass
        try:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
        except Exception:
            pass


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

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


BLOCK_SIZE = 65536


def compute_checksum(path):
    sha256 = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(BLOCK_SIZE):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, PermissionError) as e:
        print(f"[AVIS] No es pot llegir '{path}': {e}", file=sys.stderr)
        return None


def count_files(directory):
    return sum(1 for p in directory.rglob("*") if p.is_file())


def cache_path_for(directory, cache_dir):
    dir_hash = hashlib.md5(str(directory).encode()).hexdigest()[:8]
    safe_name = directory.name[:30].replace(" ", "_")
    return cache_dir / f"cache_{safe_name}_{dir_hash}.json"


def default_cache_dir():
    return Path.cwd() / "cache"


def load_cache(cache_file):
    if not cache_file.exists():
        return {}
    try:
        with open(cache_file, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[AVIS] No s ha pogut carregar la cache '{cache_file}': {e}", file=sys.stderr)
        return {}


def save_cache(cache_file, data):
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[AVIS] No s ha pogut desar la cache '{cache_file}': {e}", file=sys.stderr)


def cache_is_synchronized(directory, cache_data):
    """
    Comprova si la cache reflecteix exactament l'estat actual del disc.
    Es valida directori, existència dels fitxers i metadades bàsiques (mtime i mida).
    """
    if not cache_data:
        return False, "sense dades de cache"

    if cache_data.get("directori") != str(directory):
        return False, "directori de cache diferent"

    cached_files = cache_data.get("fitxers")
    if not isinstance(cached_files, dict):
        return False, "format de cache invalid"

    disk_files = {}
    try:
        for file_path in directory.rglob("*"):
            if not file_path.is_file():
                continue
            rel = str(file_path.relative_to(directory))
            stat = file_path.stat()
            disk_files[rel] = {"mtime": stat.st_mtime, "mida": stat.st_size}
    except OSError as e:
        return False, f"error llegint directori: {e}"

    if len(disk_files) != len(cached_files):
        return False, "nombre de fitxers diferent"

    for rel, disk_info in disk_files.items():
        cached_info = cached_files.get(rel)
        if not cached_info:
            return False, f"fitxer nou o no cachejat: {rel}"
        if cached_info.get("mtime") != disk_info["mtime"]:
            return False, f"mtime diferent: {rel}"
        if cached_info.get("mida") != disk_info["mida"]:
            return False, f"mida diferent: {rel}"
        if not cached_info.get("checksum"):
            return False, f"checksum absent: {rel}"

    return True, "ok"


def load_validated_cache(directory, cache_file):
    if not cache_file.exists():
        print(f"[AVIS] No s'ha trobat la cache esperada: '{cache_file}'", file=sys.stderr)
        return {}, "cache inexistent o buida"

    cache_data = load_cache(cache_file)
    if not cache_data:
        return {}, "cache inexistent o buida"

    synchronized, reason = cache_is_synchronized(directory, cache_data)
    if synchronized:
        return cache_data, "cache valida"

    print(
        f"[AVIS] Cache desalineada per '{directory}'. Motiu: {reason}. Es regenerara.",
        file=sys.stderr,
    )
    return {}, reason


def cached_directories_in(cache_dir):
    cache_dir = Path(cache_dir)
    if not cache_dir.is_dir():
        return []

    cached_directories = []
    seen = set()
    for cache_file in sorted(cache_dir.glob("cache_*.json")):
        cache_data = load_cache(cache_file)
        directory = cache_data.get("directori") if cache_data else None
        if not isinstance(directory, str) or not directory:
            continue
        if directory in seen:
            continue
        seen.add(directory)
        cached_directories.append(directory)

    return sorted(cached_directories, key=str.lower)


def scan_directory(directory, total, cache_data):
    cached_files = cache_data.get("fitxers", {})
    new_files = {}
    result = {}
    processed = 0
    reused = 0

    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue
        rel = str(file_path.relative_to(directory))
        try:
            stat = file_path.stat()
            mtime = stat.st_mtime
            size = stat.st_size
        except OSError:
            processed += 1
            continue

        cached = cached_files.get(rel)
        if cached and cached.get("mtime") == mtime and cached.get("mida") == size:
            checksum = cached["checksum"]
            reused += 1
        else:
            checksum = compute_checksum(file_path)
            if checksum is None:
                processed += 1
                continue

        new_files[rel] = {"checksum": checksum, "mtime": mtime, "mida": size}
        result[rel] = checksum
        processed += 1
        pct = processed * 100 // total if total else 100
        if processed % 100 == 0 or processed == total:
            print(f"\r  {processed}/{total} fitxers ({pct}%) [{reused} de cache]   ", end="", file=sys.stderr)

    print(file=sys.stderr)
    updated_cache = {
        "directori": str(directory),
        "ultim_escaneig": datetime.now().isoformat(timespec="seconds"),
        "fitxers": new_files,
    }
    return result, updated_cache


def _cerca_desti_existent(target_root, any_, mes, dia):
    """
    Busca dins el desti si ja existeix un directori adequat per a
    aquesta data, seguint dues regles (per aquest ordre de prioritat).
    """
    exact_re = re.compile(r'^(\d{4})_(\d{2})_(\d{2})(?:[ _\-].*)?$')
    range_re = re.compile(r'^(\d{4})_(\d{2})_(\d{2})-(\d{2})(?:[ _\-].*)?$')

    dirs_a_cercar = []
    year_dir = target_root / str(any_)
    if year_dir.is_dir():
        dirs_a_cercar.append(year_dir)
    if target_root.is_dir():
        dirs_a_cercar.append(target_root)

    exact_candidats = []
    rang_candidats = []

    for base_dir in dirs_a_cercar:
        try:
            subdirs = sorted(p for p in base_dir.iterdir() if p.is_dir())
        except OSError:
            continue

        for d in subdirs:
            rm = range_re.match(d.name)
            if rm:
                y, mo, d1, d2 = (int(g) for g in rm.groups())
                if y == any_ and mo == mes and d1 <= dia <= d2:
                    try:
                        rang_candidats.append((d.stat().st_mtime, d))
                    except OSError:
                        pass
                continue

            em = exact_re.match(d.name)
            if em:
                y, mo, dd = int(em.group(1)), int(em.group(2)), int(em.group(3))
                if y == any_ and mo == mes and dd == dia:
                    try:
                        exact_candidats.append((d.stat().st_mtime, d))
                    except OSError:
                        pass

    if exact_candidats:
        _, trobat = max(exact_candidats, key=lambda t: t[0])
        return trobat.relative_to(target_root)
    if rang_candidats:
        _, trobat = max(rang_candidats, key=lambda t: t[0])
        return trobat.relative_to(target_root) / f"{any_}_{mes:02d}_{dia:02d}"
    return None


def data_a_path(filename, target_root=None):
    filename = Path(filename).name
    match = re.search(r'_(\d{8})_', filename)
    if not match:
        return None

    data = datetime.strptime(match.group(1), "%Y%m%d")
    any_, mes, dia = data.year, data.month, data.day

    if target_root is not None:
        trobat = _cerca_desti_existent(Path(target_root), any_, mes, dia)
        if trobat is not None:
            return trobat

    return Path(str(any_)) / f"{any_}_{mes:02d}_{dia:02d}"

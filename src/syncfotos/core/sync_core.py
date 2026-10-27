from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


BLOCK_SIZE = 65536
MTIME_TOLERANCE_SECONDS = 2.0
CHECKSUM_VERSION = 2
IMAGE_CHECKSUM_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


def _should_skip_cache_file(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".db-wal") or name.endswith(".db-shm") or name.endswith(".db-journal")


def _cache_metadata(stat):
    return {
        "mtime": stat.st_mtime,
        "mida": stat.st_size,
        "ctime_ns": stat.st_ctime_ns,
        "dev": stat.st_dev,
        "ino": stat.st_ino,
    }


def compute_checksum(path):
    path = Path(path)
    if path.suffix.lower() in IMAGE_CHECKSUM_EXTENSIONS:
        try:
            from PIL import Image, ImageOps

            sha256 = hashlib.sha256(b"syncfotos-image-pixels-v1\0")
            with Image.open(path) as image:
                frame_count = getattr(image, "n_frames", 1)
                sha256.update(frame_count.to_bytes(4, "big"))
                for frame_index in range(frame_count):
                    image.seek(frame_index)
                    frame = ImageOps.exif_transpose(image).convert("RGBA")
                    sha256.update(frame.width.to_bytes(4, "big"))
                    sha256.update(frame.height.to_bytes(4, "big"))
                    # Per franges: mateix flux de bytes sense duplicar el fotograma sencer.
                    for top in range(0, frame.height, 256):
                        band = frame.crop((0, top, frame.width, min(top + 256, frame.height)))
                        sha256.update(band.tobytes())
            return sha256.hexdigest()
        except (ImportError, OSError, ValueError):
            pass

    sha256 = hashlib.sha256()
    try:
        with path.open("rb") as f:
            while chunk := f.read(BLOCK_SIZE):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, PermissionError) as e:
        print(f"[AVIS] No es pot llegir '{path}': {e}", file=sys.stderr)
        return None


def count_files(directory):
    return sum(1 for p in directory.rglob("*") if p.is_file() and not _should_skip_cache_file(p))


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
    if cache_data.get("checksum_version") != CHECKSUM_VERSION:
        return False, "versio de checksum diferent"

    cached_files = cache_data.get("fitxers")
    if not isinstance(cached_files, dict):
        return False, "format de cache invalid"

    disk_files = {}
    try:
        for file_path in directory.rglob("*"):
            if not file_path.is_file():
                continue
            if _should_skip_cache_file(file_path):
                continue
            rel = str(file_path.relative_to(directory))
            disk_files[rel] = _cache_metadata(file_path.stat())
    except OSError as e:
        return False, f"error llegint directori: {e}"

    if len(disk_files) != len(cached_files):
        return False, "nombre de fitxers diferent"

    for rel, disk_info in disk_files.items():
        cached_info = cached_files.get(rel)
        if not cached_info:
            return False, f"fitxer nou o no cachejat: {rel}"
        cached_mtime = cached_info.get("mtime")
        disk_mtime = disk_info["mtime"]
        try:
            mtime_delta = abs(float(cached_mtime) - float(disk_mtime))
        except (TypeError, ValueError):
            return False, f"mtime invalid: {rel}"
        if mtime_delta > MTIME_TOLERANCE_SECONDS:
            return False, f"mtime diferent: {rel}"
        if cached_info.get("mida") != disk_info["mida"]:
            return False, f"mida diferent: {rel}"
        for key in ("ctime_ns", "dev", "ino"):
            if cached_info.get(key) != disk_info[key]:
                return False, f"{key} diferent o absent: {rel}"
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

    if reason in {"directori de cache diferent", "format de cache invalid", "versio de checksum diferent"}:
        print(
            f"[AVIS] Cache desalineada per '{directory}'. Motiu: {reason}. Es regenerara.",
            file=sys.stderr,
        )
        return {}, reason

    print(
        f"[AVIS] Cache desalineada per '{directory}'. Motiu: {reason}. S'aprofitara parcialment.",
        file=sys.stderr,
    )
    return cache_data, f"cache parcial ({reason})"


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
    cached_files = (
        cache_data.get("fitxers", {})
        if cache_data.get("checksum_version") == CHECKSUM_VERSION
        else {}
    )
    new_files = {}
    result = {}
    processed = 0
    reused = 0
    reused_moved = 0
    skipped_volatile = 0

    moved_candidates = {}
    for rel, info in cached_files.items():
        checksum = info.get("checksum")
        if not checksum:
            continue
        try:
            key = (
                Path(rel).name,
                float(info.get("mtime")),
                int(info.get("mida")),
                int(info.get("dev")),
                int(info.get("ino")),
                int(info.get("ctime_ns")),
            )
        except (TypeError, ValueError):
            continue
        moved_candidates.setdefault(key, set()).add(checksum)

    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue
        if _should_skip_cache_file(file_path):
            skipped_volatile += 1
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
        cached_mtime = cached.get("mtime") if cached else None
        same_mtime = False
        if cached_mtime is not None:
            try:
                same_mtime = float(cached_mtime) == float(mtime)
            except (TypeError, ValueError):
                same_mtime = False

        same_identity = cached and all(
            cached.get(key) == value
            for key, value in (
                ("ctime_ns", stat.st_ctime_ns),
                ("dev", stat.st_dev),
                ("ino", stat.st_ino),
            )
        )

        if cached and same_mtime and cached.get("mida") == size and same_identity:
            checksum = cached["checksum"]
            reused += 1
        else:
            moved_key = (
                file_path.name,
                float(mtime),
                int(size),
                int(stat.st_dev),
                int(stat.st_ino),
                int(stat.st_ctime_ns),
            )
            candidate_checksums = moved_candidates.get(moved_key, set())
            if len(candidate_checksums) == 1:
                checksum = next(iter(candidate_checksums))
                reused += 1
                reused_moved += 1
            else:
                checksum = compute_checksum(file_path)
                if checksum is None:
                    processed += 1
                    continue

        new_files[rel] = {"checksum": checksum, **_cache_metadata(stat)}
        result[rel] = checksum
        processed += 1
        pct = processed * 100 // total if total else 100
        if processed % 100 == 0 or processed == total:
            print(f"\r  {processed}/{total} fitxers ({pct}%) [{reused} de cache]   ", end="", file=sys.stderr)

    print(file=sys.stderr)
    if skipped_volatile:
        print(f"  [INFO] Fitxers volatils ignorats: {skipped_volatile}", file=sys.stderr)
    if reused_moved:
        print(f"  [INFO] Fitxers reaprofitats per moviment: {reused_moved}", file=sys.stderr)
    updated_cache = {
        "directori": str(directory),
        "checksum_version": CHECKSUM_VERSION,
        "ultim_escaneig": datetime.now().isoformat(timespec="seconds"),
        "fitxers": new_files,
    }
    return result, updated_cache


def _cerca_desti_existent(target_root, any_, mes, dia):
    """
    Busca dins el desti si ja existeix un directori adequat per a
    aquesta data, seguint dues regles (per aquest ordre de prioritat).
    """
    candidats = _destins_per_data(target_root, any_, mes, dia)
    return candidats[0].relative_to(target_root) if candidats else None


def _destins_per_data(target_root, any_, mes, dia, include_range_directories=False):
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

    exact_candidats.sort(key=lambda t: t[0], reverse=True)
    rang_candidats.sort(key=lambda t: t[0], reverse=True)
    candidats = [path for _, path in exact_candidats]
    if include_range_directories:
        candidats.extend(path for _, path in rang_candidats)
    candidats.extend(path / f"{any_}_{mes:02d}_{dia:02d}" for _, path in rang_candidats)
    unics = []
    vistos = set()
    for path in candidats:
        key = str(path).casefold()
        if key not in vistos:
            vistos.add(key)
            unics.append(path)
    return unics


_NAME_DATE_PATTERNS = (
    # 2025-02-10 19.47.59
    re.compile(r'(?<!\d)(\d{4})-(\d{2})-(\d{2})[ _T](\d{2})[.:\-](\d{2})[.:\-](\d{2})(?!\d)'),
    # PXL_20250101_100000...
    re.compile(r'_(\d{4})(\d{2})(\d{2})_(?:(\d{2})(\d{2})(\d{2}))?'),
)


def data_del_nom(filename):
    """Retorna el datetime deduit del nom del fitxer (hora 00:00:00 si no n'hi ha) o None."""
    name = Path(filename).name
    for pattern in _NAME_DATE_PATTERNS:
        match = pattern.search(name)
        if not match:
            continue
        parts = [int(g) if g else 0 for g in match.groups()]
        try:
            return datetime(*parts)
        except ValueError:
            continue
    return None


def data_a_path(filename, target_root=None):
    data = data_del_nom(filename)
    if data is None:
        return None
    any_, mes, dia = data.year, data.month, data.day

    if target_root is not None:
        trobat = _cerca_desti_existent(Path(target_root), any_, mes, dia)
        if trobat is not None:
            return trobat

    return Path(str(any_)) / f"{any_}_{mes:02d}_{dia:02d}"


def directoris_per_data(target_root, filename):
    """Retorna tots els destins compatibles amb la data del nom, o el desti per defecte."""
    data = data_del_nom(filename)
    if data is None:
        return []
    target_root = Path(target_root)
    date_dir = f"{data.year}_{data.month:02d}_{data.day:02d}"
    default_destination = target_root / str(data.year) / date_dir
    matched_directories = _destins_per_data(
        target_root, data.year, data.month, data.day, include_range_directories=True
    )
    if matched_directories:
        candidates = []
        for directory in matched_directories:
            candidates.append(directory)
            if directory.is_dir():
                try:
                    candidates.extend(sorted(
                        path for path in directory.rglob("*") if path.is_dir()
                    ))
                except OSError:
                    pass
        unique_candidates = []
        seen = set()
        for path in candidates:
            key = str(path).casefold()
            if key not in seen:
                seen.add(key)
                unique_candidates.append(path)
        date_prefix = date_dir
        found_date_directory = any(
            path.exists()
            and (path.name == date_prefix or path.name.startswith(date_prefix + " ")
                 or path.name.startswith(date_prefix + "_") or path.name.startswith(date_prefix + "-"))
            for path in matched_directories
        )
        if not found_date_directory:
            unique_candidates.append(default_destination)
        return unique_candidates
    return [default_destination]

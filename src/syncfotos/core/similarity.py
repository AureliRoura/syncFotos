from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .sync_core import data_del_nom

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

TIME_WINDOW_SECONDS = 10 * 60
GPS_MAX_DISTANCE_M = 200.0
MAX_CANDIDATES = 200

# (acceptacio directa, zona dubtosa) per cada tipus d'embedding.
DINO_THRESHOLDS = (0.88, 0.65)
# L'embedding simple nomes detecta duplicats quasi identics: SIFT confirma la resta.
FALLBACK_THRESHOLDS = (0.90, -1.0)

# Per sota d'~50 inliers SIFT dona falsos positius (escenes diferents amb textures semblants).
MIN_INLIERS = 50
MAX_SIFT_CHECKS = 40

_EXIF_IFD = 0x8769
_GPS_IFD = 0x8825
_DATE_ORIGINAL = 36867

_dino = {"tried": False, "model": None, "processor": None, "torch": None, "device": "cpu"}


@dataclass
class SimilarMatch:
    path: Path
    score: float
    verified: bool
    inliers: int = 0


def is_image(path: Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def _open_rgb(path: Path):
    from PIL import Image, ImageOps

    with Image.open(path) as img:
        img.draft("RGB", (1024, 1024))  # decodifica JPEG a mida reduida
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")


def _dms_to_deg(dms, ref) -> float:
    d, m, s = (float(x) for x in dms)
    value = d + m / 60.0 + s / 3600.0
    return -value if str(ref).upper() in {"S", "W"} else value


def read_metadata(path: Path) -> tuple[datetime, tuple[float, float] | None]:
    """Retorna (data, gps). Data: EXIF, si no el nom del fitxer, si no mtime."""
    taken = None
    gps = None
    try:
        from PIL import Image

        with Image.open(path) as img:
            exif = img.getexif()
            raw = exif.get_ifd(_EXIF_IFD).get(_DATE_ORIGINAL) or exif.get(306)
            if raw:
                taken = datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S")
            g = exif.get_ifd(_GPS_IFD)
            if g and 2 in g and 4 in g:
                gps = (_dms_to_deg(g[2], g.get(1, "N")), _dms_to_deg(g[4], g.get(3, "E")))
    except Exception:
        pass

    if taken is None:
        taken = data_del_nom(path)
    if taken is None:
        taken = datetime.fromtimestamp(Path(path).stat().st_mtime)
    return taken, gps


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


def _load_dino():
    if _dino["tried"]:
        return _dino["model"] is not None
    _dino["tried"] = True
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModel

        _dino["processor"] = AutoImageProcessor.from_pretrained("facebook/dinov2-small")
        model = AutoModel.from_pretrained("facebook/dinov2-small")
        model.eval()
        _dino["device"] = "cuda" if torch.cuda.is_available() else "cpu"
        _dino["model"] = model.to(_dino["device"])
        _dino["torch"] = torch
    except Exception as e:
        print(f"[AVIS] DINOv2 no disponible ({e}); s'usa un embedding simple.", file=sys.stderr)
    return _dino["model"] is not None


def _embed(path: Path, use_dino: bool):
    import numpy as np

    img = _open_rgb(path)
    if use_dino:
        torch = _dino["torch"]
        inputs = _dino["processor"](images=img, return_tensors="pt").to(_dino["device"])
        with torch.no_grad():
            vec = _dino["model"](**inputs).last_hidden_state[:, 0][0].cpu().numpy()
    else:
        vec = np.asarray(img.resize((16, 16)), dtype="float32").ravel()
        vec = vec - vec.mean()
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm else vec


_sift_cache: dict = {}


def _sift_features(path: Path):
    import cv2
    import numpy as np

    key = str(path)
    if key not in _sift_cache:
        arr = np.asarray(_open_rgb(path).convert("L"))
        scale = 1024.0 / max(arr.shape)
        if scale < 1:
            arr = cv2.resize(arr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        kp, des = cv2.SIFT_create(nfeatures=3000).detectAndCompute(arr, None)
        _sift_cache[key] = ([k.pt for k in kp], des)
        if len(_sift_cache) > 300:
            _sift_cache.pop(next(iter(_sift_cache)))
    return _sift_cache[key]


def _sift_inliers(path_a: Path, path_b: Path) -> int:
    """Confirma geometricament amb SIFT + RANSAC. Retorna nombre d'inliers (0 si falla, -1 sense OpenCV)."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return -1

    pts_a, des_a = _sift_features(path_a)
    pts_b, des_b = _sift_features(path_b)
    if des_a is None or des_b is None or len(pts_a) < 8 or len(pts_b) < 8:
        return 0
    pairs = cv2.BFMatcher().knnMatch(des_a, des_b, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    if len(good) < 8:
        return 0
    src = np.float32([pts_a[m.queryIdx] for m in good]).reshape(-1, 1, 2)
    dst = np.float32([pts_b[m.trainIdx] for m in good]).reshape(-1, 1, 2)
    _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    return int(mask.sum()) if mask is not None else 0


def find_similar(reference: Path, candidates: list[Path]) -> list[SimilarMatch]:
    """Pipeline: temps -> GPS -> embeddings -> SIFT/RANSAC per als dubtosos."""
    import numpy as np

    reference = Path(reference)
    ref_time, ref_gps = read_metadata(reference)

    near = []
    for cand in candidates:
        cand = Path(cand)
        try:
            c_time, c_gps = read_metadata(cand)
        except OSError:
            continue
        delta = abs((c_time - ref_time).total_seconds())
        if delta > TIME_WINDOW_SECONDS:
            continue
        if ref_gps and c_gps and _haversine_m(ref_gps, c_gps) > GPS_MAX_DISTANCE_M:
            continue
        near.append((delta, cand))
    near.sort(key=lambda t: t[0])
    near = [c for _, c in near[:MAX_CANDIDATES]]
    if not near:
        return []

    use_dino = _load_dino()
    accept, doubt = DINO_THRESHOLDS if use_dino else FALLBACK_THRESHOLDS
    ref_vec = _embed(reference, use_dino)

    scored = []
    for cand in near:
        try:
            scored.append((float(np.dot(ref_vec, _embed(cand, use_dino))), cand))
        except Exception:
            continue
    scored.sort(key=lambda t: t[0], reverse=True)

    matches = []
    sift_checks = 0
    for score, cand in scored:
        if score >= accept:
            matches.append(SimilarMatch(cand, score, verified=True))
        elif score >= doubt and sift_checks < MAX_SIFT_CHECKS:
            sift_checks += 1
            inliers = _sift_inliers(reference, cand)
            if inliers >= MIN_INLIERS:
                matches.append(SimilarMatch(cand, score, verified=True, inliers=inliers))
            elif inliers < 0:
                matches.append(SimilarMatch(cand, score, verified=False))
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches

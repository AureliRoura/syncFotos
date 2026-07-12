from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil


@dataclass
class ReviewState:
    idx: int = 0
    last_dir: Path | None = None
    mogudes: int = 0
    saltades: int = 0
    historial: list[tuple[Path, Path]] = field(default_factory=list)


def create_review_state(target_root: Path) -> ReviewState:
    return ReviewState(last_dir=target_root)


def unique_destination(dest_dir: Path, source_name: str) -> Path:
    dest_file = dest_dir / source_name
    if not dest_file.exists():
        return dest_file

    stem = Path(source_name).stem
    suffix = Path(source_name).suffix
    index = 1
    while dest_file.exists():
        dest_file = dest_dir / f"{stem}_{index}{suffix}"
        index += 1
    return dest_file


def move_missing_file(source_root: Path, rel_path: Path, dest_dir: Path, state: ReviewState) -> tuple[Path, Path]:
    full_path = source_root / rel_path
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = unique_destination(dest_dir, full_path.name)
    shutil.move(str(full_path), dest_file)
    state.historial.append((full_path, dest_file))
    state.last_dir = dest_dir
    state.mogudes += 1
    state.idx += 1
    return full_path, dest_file


def restore_recent_moves(selected_moves: list[tuple[Path, Path]], state: ReviewState) -> list[tuple[Path, Path]]:
    restored: list[tuple[Path, Path]] = []
    for orig, dest in selected_moves:
        orig.parent.mkdir(parents=True, exist_ok=True)
        target_name = orig
        if target_name.exists():
            stem = orig.stem
            suffix = orig.suffix
            index = 1
            while target_name.exists():
                target_name = orig.parent / f"{stem}_{index}{suffix}"
                index += 1
        shutil.move(str(dest), target_name)
        restored.append((orig, dest))

    for orig, dest in restored:
        try:
            state.historial.remove((orig, dest))
        except ValueError:
            pass
        state.mogudes -= 1
        state.idx = max(0, state.idx - 1)

    return restored

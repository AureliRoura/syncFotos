from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import tempfile


@dataclass
class ReviewState:
    idx: int = 0
    last_dir: Path | None = None
    mogudes: int = 0
    saltades: int = 0
    eliminades: int = 0
    historial: list[tuple[str, Path, Path]] = field(default_factory=list)
    trash_dir: Path | None = None


def create_review_state(target_root: Path) -> ReviewState:
    trash_dir = Path(tempfile.mkdtemp(prefix="syncfotos_review_trash_"))
    return ReviewState(last_dir=target_root, trash_dir=trash_dir)


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
    state.historial.append(("move", full_path, dest_file))
    state.last_dir = dest_dir
    state.mogudes += 1
    state.idx += 1
    return full_path, dest_file


def delete_missing_file(source_root: Path, rel_path: Path, state: ReviewState) -> Path:
    full_path = source_root / rel_path
    if state.trash_dir is None:
        state.trash_dir = Path(tempfile.mkdtemp(prefix="syncfotos_review_trash_"))
    trash_base = state.trash_dir
    trash_dir = trash_base / Path(rel_path).parent
    trash_dir.mkdir(parents=True, exist_ok=True)
    trash_file = unique_destination(trash_dir, full_path.name)
    shutil.move(str(full_path), trash_file)
    state.historial.append(("delete", full_path, trash_file))
    state.eliminades += 1
    state.idx += 1
    return full_path


def restore_recent_actions(
    selected_actions: list[tuple[str, Path, Path]],
    state: ReviewState,
) -> list[tuple[str, Path, Path]]:
    restored: list[tuple[str, Path, Path]] = []
    for action, orig, source_path in selected_actions:
        orig.parent.mkdir(parents=True, exist_ok=True)
        target_name = orig
        if target_name.exists():
            stem = orig.stem
            suffix = orig.suffix
            index = 1
            while target_name.exists():
                target_name = orig.parent / f"{stem}_{index}{suffix}"
                index += 1
        shutil.move(str(source_path), target_name)
        restored.append((action, orig, source_path))

    for action, orig, source_path in restored:
        try:
            state.historial.remove((action, orig, source_path))
        except ValueError:
            pass
        if action == "move":
            state.mogudes = max(0, state.mogudes - 1)
        elif action == "delete":
            state.eliminades = max(0, state.eliminades - 1)
        state.idx = max(0, state.idx - 1)

    return restored


def restore_recent_moves(selected_moves: list[tuple[Path, Path]], state: ReviewState) -> list[tuple[Path, Path]]:
    restored_actions = restore_recent_actions(
        [("move", orig, dest) for orig, dest in selected_moves],
        state,
    )
    return [(orig, path) for _, orig, path in restored_actions]

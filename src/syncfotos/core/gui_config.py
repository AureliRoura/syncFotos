from __future__ import annotations

import json
import os
from pathlib import Path


def config_file_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home())) / "SyncFotos"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "syncfotos"
    return base / "gui_config.json"


def load_gui_config(path: Path | None = None) -> dict:
    config_path = path or config_file_path()
    try:
        with config_path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_gui_config(data: dict, path: Path | None = None) -> None:
    config_path = path or config_file_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_suffix(config_path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary_path, config_path)
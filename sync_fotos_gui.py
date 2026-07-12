#!/usr/bin/env python3
from pathlib import Path

from src.syncfotos.ui.sync_fotos_gui import launch_sync_fotos_gui


if __name__ == "__main__":
    launch_sync_fotos_gui(Path(__file__).resolve())

#!/usr/bin/env python3
import sys

from src.syncfotos.ui.duplicats_gui import DuplicatsApp


if __name__ == "__main__":
    cache_arg = sys.argv[1] if len(sys.argv) > 1 else None
    DuplicatsApp(cache_arg)

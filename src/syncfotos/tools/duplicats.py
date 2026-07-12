#!/usr/bin/env python3
import sys

from ..ui.duplicats_gui import DuplicatsApp


def main() -> None:
    cache_arg = sys.argv[1] if len(sys.argv) > 1 else None
    DuplicatsApp(cache_arg)


if __name__ == "__main__":
    main()

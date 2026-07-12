# SyncFotos

SyncFotos is a Python CLI tool that compares two folders by SHA-256 checksum to find files that exist in the source but not in the destination. It can also open an interactive review window to move missing photos/videos to the right location.

The script output and UI text are currently in Catalan.

## What It Does

- Scans source and destination recursively.
- Computes SHA-256 for each file.
- Uses JSON cache files to avoid recomputing unchanged checksums.
- Detects missing files based on content checksum, not filename.
- Optionally writes a report file.
- Optionally generates a PowerShell deletion script for files already present in destination.
- Optionally opens a Tkinter review UI for missing files.

## Repository Contents

- sync_fotos.py: Main CLI entry point.
- src/syncfotos/core/: Core checksum, cache, reporting, and review operations.
- src/syncfotos/ui/: Tkinter launchers for the GUI, duplicates review, and missing-file review.
- src/syncfotos/tools/: Helpers for duplicate detection and empty-file scanning.
- README.md: Project documentation.
- .gitignore: Typical Python, editor, and local data ignores.

## Requirements

- Python 3.10+ recommended.
- On Windows, the standard Python install usually includes Tkinter, which is used for the no-arguments launcher and the review window.

Optional dependencies (only needed for interactive review mode):

- Pillow: Image preview in Tkinter.
- python-vlc: Video playback in Tkinter.
- VLC Media Player installed on the system.

Install optional packages:

```bash
pip install pillow python-vlc
```

## Usage

Basic command:

```bash
python sync_fotos.py ORIGEN DESTI
```

If you run the script without arguments, it opens a Windows GUI so you can fill in the inputs by hand:

```bash
python sync_fotos.py
```

You can also launch the GUI module directly:

```bash
python -m src.syncfotos.ui.sync_fotos_gui
```

Example:

```bash
python sync_fotos.py "D:\Fotos\Mobil" "E:\Arxiu\Fotos"
```

Show help:

```bash
python sync_fotos.py --help
```

També es pot executar com a paquet (un cop instal.lat):

```bash
sync-fotos --help
sync-fotos-gui
sync-fotos-duplicats
sync-fotos-fitxers-buits "D:\\Fotos"
```

---

## Empaquetat i distribució

Construcció local del paquet:

```bash
python -m pip install --upgrade build
python -m build
```

Es generen dos artefactes a `dist/`:

* `syncfotos-<versio>.tar.gz`
* `syncfotos-<versio>-py3-none-any.whl`

Instal.lació local de prova:

```bash
python -m pip install dist/syncfotos-*.whl
```

---

## Publicació amb GitHub Actions

El workflow [`Build and Publish`](.github/workflows/release.yml) fa:

1. Build de wheel + sdist.
2. Publicació d'artefactes del build.
3. Publicació a PyPI quan fas push d'un tag `v*` (per exemple `v1.0.0`).

Passos per activar-ho:

1. A [`pyproject.toml`](pyproject.toml), canvia els URLs `OWNER/REPO` pel teu repositori real.
2. A PyPI, crea el projecte `syncfotos` (o canvia el nom a `pyproject.toml` si ja existeix).
3. Configura Trusted Publishing de PyPI per aquest repositori GitHub.
4. Fes commit i push.
5. Crea un tag de release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

---


Positional arguments:

- ORIGEN: Source directory to verify.
- DESTI: Destination directory to compare against.

Flags:

- --version: Print script version.
- --generar-sortida: Write a text report of missing files.
- --mostrar-checksum: Include checksum values in the report.
- --sortida FITXER: Custom output report path.
- --cache-dir DIR: Custom cache directory (default: ./cache).
- --netejar-cache-origen: Delete source cache file and exit.
- --script-eliminacio FITXER: Generate a .ps1 script to remove from source files already found in destination.
- --revisar: Open interactive review window for missing files.

## Windows GUI

The no-arguments launcher uses Tkinter from the Python standard library, so it does not need extra packages.

The GUI lets you enter:

- Source and destination folders.
- Cache directory.
- Optional output report path.
- Optional PowerShell deletion script path.
- The same checkboxes as the CLI flags.

## Typical Workflows

1) Compare folders and print summary only:

```bash
python sync_fotos.py "D:\Source" "E:\Backup"
```

2) Compare and generate missing-files report:

```bash
python sync_fotos.py "D:\Source" "E:\Backup" --generar-sortida
```

3) Compare, include checksums, and save report to a custom file:

```bash
python sync_fotos.py "D:\Source" "E:\Backup" --generar-sortida --mostrar-checksum --sortida "resultat.txt"
```

4) Generate deletion script for files already synced:

```bash
python sync_fotos.py "D:\Source" "E:\Backup" --script-eliminacio "eliminar_present.ps1"
```

5) Launch interactive review for missing files:

```bash
python sync_fotos.py "D:\Source" "E:\Backup" --revisar
```

Direct module entry points:

```bash
python -m src.syncfotos.ui.duplicats_gui
python -m src.syncfotos.tools.fitxers_buits D:\Fotos
```

Legacy root wrappers have been removed; use the module entry points above.

## Interactive Review Mode

When --revisar is enabled and missing files exist:

- Images: shown in a Tkinter canvas.
- Videos: played via VLC embedding.
- Actions:
	- Mou a...: move to a selected folder.
	- Mou últim: move to last used folder.
	- Data Fitxer: move to DESTI/YYYY/YYYY_MM_DD based on filename pattern _YYYYMMDD_.
	- Salta: skip current file.
	- Surt: exit review.

Date-based move works only when the filename contains _YYYYMMDD_ between underscores, for example:

- PXL_20251129_080003803.TS.mp4

This maps to:

- 2025/2025_11_29/

## Cache Behavior

- Cache files are stored as JSON in ./cache by default.
- One cache file is created per scanned directory.
- A cached checksum is reused when both file mtime and size match.

## Notes and Safety

- File comparison is checksum-based, so renamed duplicates are considered already present.
- The generated deletion script is not executed automatically.
- Always review the generated .ps1 script before running it.
- Moving files in review mode modifies your source files immediately.

## Known Gaps

- No automated tests in this repository yet.
- No packaging or installer yet.
- UI strings and messages are Catalan-only.

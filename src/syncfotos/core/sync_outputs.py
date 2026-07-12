from __future__ import annotations

from datetime import datetime
from pathlib import Path


def build_missing_and_present(source_map, target_checksums):
    missing = sorted(
        (Path(rel), checksum)
        for rel, checksum in source_map.items()
        if checksum not in target_checksums
    )
    present = sorted(
        Path(rel)
        for rel, checksum in source_map.items()
        if checksum in target_checksums
    )
    return missing, present


def write_deletion_script(script_path, source, target, present):
    script_path = Path(script_path)
    with open(script_path, "w", encoding="utf-8") as sc:
        sc.write("# Script generat per sync_fotos.py\n")
        sc.write(f"# Data:   {datetime.now().isoformat(timespec='seconds')}\n")
        sc.write(f"# Origen: {source}\n")
        sc.write(f"# Desti:  {target}\n")
        sc.write(f"# Fitxers a eliminar: {len(present)}\n")
        sc.write("#\n# ATENCIO: reviseu el fitxer abans d'executar-lo!\n\n")
        sc.write("$ErrorActionPreference = 'Stop'\n\n")
        for rel_path in present:
            full = source / rel_path
            sc.write(f'Remove-Item -LiteralPath "{full}"\n')


def write_missing_report(output_path, source, target, missing, mostrar_checksum=False):
    output_path = Path(output_path)
    with open(output_path, "w", encoding="utf-8") as out:
        out.write(f"Escaneig: {datetime.now().isoformat(timespec='seconds')}\n")
        out.write(f"Origen:   {source}\n")
        out.write(f"Desti:    {target}\n")
        out.write("=" * 60 + "\n\n")
        if not missing:
            out.write("Tots els fitxers de l'origen es troben al desti.\n")
        else:
            out.write(f"Fitxers NO trobats al desti ({len(missing)}):\n\n")
            for rel_path, checksum in missing:
                if mostrar_checksum:
                    out.write(f"  {rel_path}  [{checksum}]\n")
                else:
                    out.write(f"  {rel_path}\n")

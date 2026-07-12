#!/usr/bin/env python3
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path


import platform

from src.syncfotos.core.sync_core import (
    cache_path_for,
    data_a_path,
    load_validated_cache,
    count_files,
    scan_directory,
    save_cache,
)
from src.syncfotos.core.sync_outputs import (
    build_missing_and_present,
    write_deletion_script,
    write_missing_report,
)
from src.syncfotos.ui.review_gui import revisar_fitxers





def main():
    if len(sys.argv) == 1:
        from src.syncfotos.ui.sync_fotos_gui import launch_sync_fotos_gui

        launch_sync_fotos_gui(Path(__file__).resolve())
        return

    parser = argparse.ArgumentParser(
        description="Trova fitxers de l'origen que no es troben al desti (per checksum)."
    )
    parser.add_argument("origen", help="Directori origen (els fitxers a verificar)")
    parser.add_argument("desti", help="Directori desti (on s ha de buscar)")
    parser.add_argument("--version", action="version", version="sync_fotos.py 1.0")
    parser.add_argument("--generar-sortida", action="store_true",
                        help="Activa la generació del fitxer de sortida")
    parser.add_argument("--mostrar-checksum", action="store_true",
                        help="Inclou el checksum SHA-256 al fitxer de sortida")
    parser.add_argument("--sortida", default=None, metavar="FITXER",
                        help="Fitxer de sortida (per defecte: fitxers_mancants_YYYYMMDD_HHMMSS.txt)")
    parser.add_argument("--cache-dir", default=None, metavar="DIR",
                        help="Directori dels fitxers de control (per defecte: directori actual)")
    parser.add_argument("--netejar-cache-origen", action="store_true",
                        help="Elimina el fitxer de cache de l'origen i surt")
    parser.add_argument("--script-eliminacio", default=None, metavar="FITXER",
                        help="Genera un script .ps1 que elimina de l'origen els fitxers que JA estan al desti")
    parser.add_argument("--revisar", action="store_true",
                        help="Obre una finestra per revisar i moure les fotos mancants una a una")
    args = parser.parse_args()

    source = Path(args.origen).resolve()
    target = Path(args.desti).resolve()
    cache_dir = (
        Path(args.cache_dir).resolve()
        if args.cache_dir
        else Path.cwd() / "cache"
    )
    
    if not source.is_dir():
        print(f"Error: l'origen '{source}' no es un directori valid.", file=sys.stderr)
        sys.exit(1)

    # -- Netejar cache origen (no cal escanar res) ----------------------------
    if args.netejar_cache_origen:
        cf = cache_path_for(source, cache_dir)
        if cf.exists():
            cf.unlink()
            print(f"Cache eliminada: {cf}", file=sys.stderr)
        else:
            print(f"No hi ha cache per a aquest origen: {cf}", file=sys.stderr)
        sys.exit(0)

    if not target.is_dir():
        print(f"Error: el desti '{target}' no es un directori valid.", file=sys.stderr)
        sys.exit(1)

    # Desti
    target_cache_file = cache_path_for(target, cache_dir)
    target_cache, target_cache_status = load_validated_cache(target, target_cache_file)
    last_scan_dst = target_cache.get("ultim_escaneig", "mai")
    print(f"Escaneant desti:  {target}", file=sys.stderr)
    print(f"  Ultim escaneig: {last_scan_dst}", file=sys.stderr)
    if target_cache_status != "cache valida":
        print(f"  Estat cache:    {target_cache_status}", file=sys.stderr)
    target_total = count_files(target)
    print(f"  {target_total} fitxers trobats. Calculant checksums...", file=sys.stderr)
    target_map, updated_target_cache = scan_directory(target, target_total, target_cache)
    target_checksums = set(target_map.values())
    save_cache(target_cache_file, updated_target_cache)
    print(f"  {len(target_checksums)} checksums unics. Cache desada: {target_cache_file.name}", file=sys.stderr)

    # Origen
    source_cache_file = cache_path_for(source, cache_dir)
    source_cache, source_cache_status = load_validated_cache(source, source_cache_file)
    last_scan_src = source_cache.get("ultim_escaneig", "mai")
    print(f"\nEscaneant origen: {source}", file=sys.stderr)
    print(f"  Ultim escaneig: {last_scan_src}", file=sys.stderr)
    if source_cache_status != "cache valida":
        print(f"  Estat cache:    {source_cache_status}", file=sys.stderr)
    source_total = count_files(source)
    print(f"  {source_total} fitxers trobats. Calculant checksums...", file=sys.stderr)
    source_map, updated_source_cache = scan_directory(source, source_total, source_cache)
    save_cache(source_cache_file, updated_source_cache)
    print(f"  Cache desada: {source_cache_file.name}", file=sys.stderr)

    # Fitxers mancants i fitxers presents (sync OK)
    missing, present = build_missing_and_present(source_map, target_checksums)

    # -- Script d'eliminacio --------------------------------------------------
    if args.script_eliminacio:
        script_path = Path(args.script_eliminacio)
        write_deletion_script(script_path, source, target, present)
        print(f"Script d'eliminacio desat a: {script_path}", file=sys.stderr)
        print(f"  {len(present)} fitxers llistats per eliminar.")

    # Fitxer de sortida
    if args.generar_sortida:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(args.sortida) if args.sortida else Path.cwd() / f"fitxers_mancants_{ts}.txt"
        write_missing_report(output_path, source, target, missing, args.mostrar_checksum)
        if not missing:
            print("\nTots els fitxers de l'origen es troben al desti.")
        else:
            print(f"\n{len(missing)} fitxers mancants.")
        print(f"Resultat desat a: {output_path}", file=sys.stderr)
    
    # -- Revisio interactiva --------------------------------------------------
    if args.revisar:
        if missing:
            revisar_fitxers(missing, source, target)
        else:
            print("No hi ha fitxers mancants per revisar.", file=sys.stderr)

if __name__ == "__main__":
    main()
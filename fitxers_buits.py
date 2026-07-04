#!/usr/bin/env python3
"""
fitxers_buits.py

Cerca, dins d'un directori i tots els seus subdirectoris, tots els
fitxers que tinguin tamany 0 bytes (fitxers buits/corruptes).

Per cada fitxer trobat, guarda:
  - El path complet (nom sencer del fitxer)
  - La data de creacio
  - La data de l'ultima modificacio

El resultat es desa en un fitxer CSV.

US:
    python fitxers_buits.py <directori> [--sortida fitxer.csv]

Exemple:
    python fitxers_buits.py "D:\\Fotos"
    python fitxers_buits.py "D:\\Fotos" --sortida buits_fotos.csv

NOTA sobre la "data de creacio":
    A Windows, st_ctime es realment la data de creacio del fitxer.
    A Linux/macOS, aquest mateix camp representa la data del darrer
    canvi de metadades (no sempre la creacio original). Si aquest
    programa s'executa en un d'aquests sistemes, la data de creacio
    mostrada pot no ser exacta.
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path


def format_data(timestamp):
    """Converteix un timestamp Unix a un text llegible AAAA-MM-DD HH:MM:SS."""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def cerca_fitxers_buits(directori):
    """
    Recorre recursivament 'directori' i retorna una llista de dicts
    amb informacio dels fitxers de tamany 0 trobats.
    """
    resultats = []
    errors = []

    for path in directori.rglob("*"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError as exc:
            errors.append((path, str(exc)))
            continue

        if stat.st_size == 0:
            resultats.append({
                "path": str(path.resolve()),
                "data_creacio": format_data(stat.st_ctime),
                "data_modificacio": format_data(stat.st_mtime),
            })

    return resultats, errors


def guarda_csv(resultats, sortida):
    """Desa la llista de resultats en un fitxer CSV."""
    with open(sortida, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=["path", "data_creacio", "data_modificacio"])
        writer.writeheader()
        writer.writerows(resultats)


def main():
    parser = argparse.ArgumentParser(
        description="Cerca fitxers de tamany 0 dins d'un directori "
                     "(i subdirectoris) i guarda el resultat en un CSV.")
    parser.add_argument("directori", help="Directori on cercar")
    parser.add_argument(
        "--sortida", "-o", default=None,
        help="Fitxer CSV de sortida (per defecte: "
             "fitxers_buits_AAAAMMDD_HHMMSS.csv al directori actual)")
    args = parser.parse_args()

    directori = Path(args.directori)
    if not directori.is_dir():
        print(f"ERROR: '{directori}' no es un directori valid.")
        sys.exit(1)

    if args.sortida:
        sortida = Path(args.sortida)
    else:
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        sortida = Path(f"fitxers_buits_{marca}.csv")

    print(f"Cercant fitxers de tamany 0 a: {directori.resolve()}")
    resultats, errors = cerca_fitxers_buits(directori)

    guarda_csv(resultats, sortida)

    print(f"\nFitxers de tamany 0 trobats: {len(resultats)}")
    print(f"Resultat guardat a: {sortida.resolve()}")

    if errors:
        print(f"\nAvis: {len(errors)} fitxer(s) no s'han pogut llegir "
              f"(permisos, enllaços trencats, etc.):")
        for path, err in errors[:10]:
            print(f"  - {path}: {err}")
        if len(errors) > 10:
            print(f"  ... i {len(errors) - 10} mes.")


if __name__ == "__main__":
    main()

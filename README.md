# SyncFotos

Aplicació en Python per sincronitzar, revisar i classificar fotografies i vídeos entre dos directoris.

L'objectiu és detectar els fitxers que existeixen al directori d'origen però no al de destinació i facilitar-ne la revisió abans de moure'ls a la ubicació definitiva.

---

## Característiques

* 📷 Visualització d'imatges.
* 🎥 Reproducció de vídeos integrada amb VLC.
* ⏯ Controls de reproducció (Play/Pausa i barra de progrés).
* 🔍 Comparació entre dos directoris.
* 📂 Detecció de fitxers inexistents al directori de destinació.
* 📁 Moure fitxers a una carpeta seleccionada.
* 📁 Moure fitxers a l'última carpeta utilitzada.
* 📅 Moure fitxers automàticament segons la data deduïda del nom.
* 🖼 Obrir una fotografia amb un editor extern.
* 💬 Tooltips amb informació sobre el directori de destinació.

---

## Organització automàtica per data

Si el fitxer té un nom com:

```text
PXL_20251129_080003803.TS.mp4
```

SyncFotos detecta la data (`2025-11-29`) i proposa moure'l a:

```text
2025/
└── 2025_11_29/
```

Si el nom del fitxer no conté una data reconeguda, aquesta opció no es mostra.

---

## Requisits

* Python 3.11 o superior
* VLC Media Player instal·lat

Llibreries Python:

```bash
pip install pillow python-vlc opencv-python
```

---

## Execució

```bash
python sync_fotos.py
```

Per veure totes les opcions disponibles:

```bash
python sync_fotos.py --help
```

---

## Flux de treball

1. Compara el directori origen amb el directori destinació.
2. Detecta els fitxers que falten.
3. Mostra cada fitxer (foto o vídeo).
4. L'usuari pot:

* Moure'l a una carpeta.
* Moure'l a l'última carpeta utilitzada.
* Moure'l segons la data del nom.
* Obrir-lo amb un editor.
* Saltar-lo.

5. En finalitzar es mostra un resum de les accions realitzades.

---

## Llibreries utilitzades

* argparse
* pathlib
* shutil
* tkinter
* Pillow
* python-vlc
* OpenCV
* datetime
* re

---

## Estructura del projecte

```text
syncFotos/
│
├── sync_fotos.py
├── README.md
├── .gitignore
├── cache/
└── ...
```

---

## Funcionalitats previstes

* [ ] Configuració persistent.
* [ ] Selecció de l'editor d'imatges des de la interfície.
* [ ] Dreceres de teclat.
* [ ] Millorar la reproducció de vídeos.
* [ ] Suport per a més formats de noms de fitxer.
* [ ] Generació d'un executable per a Windows.

---

## Captura de pantalla

Es recomana afegir una o més captures de la interfície aquí.

```markdown
![Captura principal](docs/screenshot.png)
```

---

## Llicència

Aquest projecte es distribueix sota la llicència MIT.

---

## Autor

Desenvolupat com a eina personal per facilitar l'organització de fotografies i vídeos.

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
* VLC Media Player instal·lat per reproduir vídeos a la interfície
```
El paquet instal·la automàticament les seves dependències Python (`Pillow`, `python-vlc` i `opencv-python`).

## Instal·lació i execució

Un cop publicat a PyPI, instal·la SyncFotos amb:
SyncFotos detecta la data (`2025-11-29`) i proposa moure'l a:

python -m pip install syncfotos
2025/
└── 2025_11_29/
Després de la instal·lació, les ordres queden disponibles directament al terminal:

Si el nom del fitxer no conté una data reconeguda, aquesta opció no es mostra.
# Interfície gràfica principal
sync-fotos-gui

# També obre la interfície gràfica si no es passen arguments
sync-fotos

# Comparació per terminal (origen i destinació són obligatoris)
sync-fotos "D:\\Fotos\\Origen" "D:\\Fotos\\Desti" --generar-sortida

# Eines addicionals
sync-fotos-duplicats
sync-fotos-fitxers-buits "D:\\Fotos"
---

Per consultar les opcions de la comparació:

* Python 3.11 o superior
sync-fotos --help

Llibreries Python:
Per instal·lar i provar el codi del repositori sense publicar-lo a PyPI:
```bash
pip install pillow python-vlc opencv-python
python -m pip install .
## Execució

També es pot instal·lar en mode editable durant el desenvolupament amb `python -m pip install -e .`.

## Construcció i pujada a PyPI
python sync_fotos.py
La versió del paquet es determina a partir del tag Git `vX.Y.Z`. Crea un tag nou per a cada versió i no reutilitzis una versió ja publicada.

Per construir i comprovar els artefactes localment:

Per veure totes les opcions disponibles:
python -m pip install --upgrade build twine
```bash
python -m twine check dist/*
python sync_fotos.py --help
```
Es generen a `dist/` un paquet `.whl` i un arxiu `.tar.gz`. Per pujar-los manualment a PyPI:
També es pot executar com a paquet (un cop instal.lat):
```bash
python -m twine upload dist/*
```
sync-fotos --help
Per fer primer una prova a TestPyPI, configura-hi un compte i executa:
sync-fotos-duplicats
sync-fotos-fitxers-buits "D:\\Fotos"
python -m twine upload --repository testpypi dist/*

---
### Publicació automàtica amb GitHub Actions
## Empaquetat i distribució
El workflow [`Build and Publish`](.github/workflows/release.yml) construeix els artefactes i els publica a PyPI quan s'envia un tag `v*`.
Construcció local del paquet:
Per activar-ho:
python -m build
1. Comprova que el nom `syncfotos` estigui disponible a PyPI.
2. A la configuració de PyPI, afegeix aquest repositori GitHub com a Trusted Publisher, indicant l'organització/usuari, el repositori i el workflow `.github/workflows/release.yml`.
3. Envia els canvis al repositori i crea/envia un tag de versió:

	```bash
	git tag v1.0.0
	git push origin v1.0.0
	```

El workflow publica automàticament la versió corresponent al tag. No cal crear un token d'API de PyPI quan s'utilitza Trusted Publishing.
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

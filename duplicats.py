#!/usr/bin/env python3
"""
duplicats.py — Eina gràfica per trobar i gestionar fitxers duplicats
               (fotos i vídeos) a partir d'un fitxer de cache generat
               per sync_fotos.py

Ús:
    python duplicats.py [fitxer_cache.json]

Si no s'indica el fitxer, s'obre un diàleg per seleccionar-lo.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff", ".tif"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v", ".3gp",
              ".flv", ".wmv", ".mts", ".m2ts", ".ts"}


# ── helpers ───────────────────────────────────────────────────────────────────

def load_cache(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_duplicate_groups(cache_data, root_dir):
    """
    Retorna una llista de tuples (checksum, [rel_path, rel_path, ...])
    per a cada grup de fotos/vídeos duplicats trobats a la cache
    (un grup pot tenir 2 o més fitxers amb el mateix checksum).
    Només es consideren fitxers amb extensions d'imatge o vídeo, i
    NOMÉS els que realment existeixen al disc en aquest moment: un
    fitxer que consta a la cache però que ja no hi és (esborrat,
    mogut, disc extern desconnectat, etc.) es descarta i no es
    considera duplicat de res.

    Retorna (groups, missing_count) on missing_count és el nombre de
    fitxers de la cache que s'han descartat per no existir al disc.
    """
    fitxers = cache_data.get("fitxers", {})
    media_exts = IMAGE_EXTS | VIDEO_EXTS
    by_checksum = defaultdict(list)
    missing_count = 0

    for rel_path, info in fitxers.items():
        if Path(rel_path).suffix.lower() not in media_exts:
            continue
        chk = info.get("checksum")
        if not chk:
            continue
        if not (root_dir / rel_path).exists():
            missing_count += 1
            continue
        by_checksum[chk].append(rel_path)

    groups = []
    for chk, paths in by_checksum.items():
        if len(paths) >= 2:
            groups.append((chk, sorted(paths)))
    return groups, missing_count


def format_size(size_bytes):
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def format_mtime(mtime):
    try:
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d  %H:%M:%S")
    except Exception:
        return "Desconegut"


# ── aplicació principal ───────────────────────────────────────────────────────

class DuplicatsApp:

    # paleta de colors
    BG     = "#1e1e1e"
    BG2    = "#252525"
    BG3    = "#2a2a2a"
    BG4    = "#161616"
    FG     = "#ffffff"
    FG2    = "#cccccc"
    FG3    = "#aaaaaa"
    RED    = "#c0392b"
    GREEN  = "#27AE60"
    BLUE   = "#2E86C1"
    ORANGE = "#e67e22"
    GRAY   = "#5d6d7e"

    def __init__(self, cache_file=None):
        self.cache_data = {}
        self.root_dir = Path(".")
        self.groups = []          # [(chk, [rel_1, rel_2, ...]), ...]
        self.missing_count = 0    # fitxers de la cache descartats per no existir al disc
        self.group_idx = 0
        self.current_files = []   # fitxers del grup actual (llista mutable de "vius")
        self.survivor = None      # fitxer "supervivent" actual del grup (costat esquerre)
        self.cand_idx = None      # índex dins current_files del candidat a comparar (costat dret)
        self.deleted = 0
        self.skipped = 0
        self.deleted_files = set()
        self._img_refs = [None, None]

        self.root = tk.Tk()
        self.root.title("Gestor de Duplicats")
        self.root.geometry("1280x840")
        self.root.minsize(900, 640)
        self.root.configure(bg=self.BG)
        self._set_icon()

        if cache_file:
            self._load_cache_file(Path(cache_file))
        else:
            self._show_welcome()

        self.root.mainloop()

    def _set_icon(self):
        try:
            # Icona senzilla (quadrat de color)
            img = tk.PhotoImage(width=32, height=32)
            img.put("#2E86C1", to=(0, 0, 32, 32))
            self.root.iconphoto(True, img)
        except Exception:
            pass

    # ── utilitats ─────────────────────────────────────────────────────────────

    def _clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def _center_window(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w  = self.root.winfo_width()
        h  = self.root.winfo_height()
        self.root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    # ── pantalla de benvinguda ────────────────────────────────────────────────

    def _show_welcome(self):
        self._clear()

        frame = tk.Frame(self.root, bg=self.BG)
        frame.place(relx=0.5, rely=0.45, anchor=tk.CENTER)

        tk.Label(frame, text="Gestor de Fitxers Duplicats",
                 bg=self.BG, fg=self.FG,
                 font=("Segoe UI", 24, "bold")).pack(pady=(0, 8))

        tk.Label(frame,
                 text="Detecta i elimina fotos i vídeos duplicats\n"
                      "a partir d'un fitxer de cache de sync_fotos.py",
                 bg=self.BG, fg=self.FG3,
                 font=("Segoe UI", 12),
                 justify=tk.CENTER).pack(pady=(0, 50))

        tk.Button(frame, text="  Obrir fitxer de cache…  ",
                  command=self._browse_cache,
                  bg=self.BLUE, fg="white",
                  font=("Segoe UI", 13, "bold"),
                  padx=24, pady=14,
                  relief=tk.FLAT, cursor="hand2").pack()

        self._center_window()

    def _browse_cache(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Selecciona el fitxer de cache",
            filetypes=[("Fitxers JSON", "*.json"), ("Tots els fitxers", "*.*")],
        )
        if path:
            self._load_cache_file(Path(path))

    # ── càrrega i pantalla d'informació ───────────────────────────────────────

    def _load_cache_file(self, path):
        try:
            self.cache_data = load_cache(path)
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Error",
                                 f"No s'ha pogut llegir el fitxer:\n{exc}",
                                 parent=self.root)
            return

        self.root_dir = Path(self.cache_data.get("directori", "."))
        self.groups, self.missing_count = find_duplicate_groups(
            self.cache_data, self.root_dir)
        self._show_info_screen()

    def _show_info_screen(self):
        self._clear()

        directori      = self.cache_data.get("directori", "Desconegut")
        ultim_escaneig = self.cache_data.get("ultim_escaneig", "Desconegut")
        num_fitxers    = len(self.cache_data.get("fitxers", {}))
        num_grups      = len(self.groups)
        num_pairs      = sum(len(files) - 1 for _, files in self.groups)

        outer = tk.Frame(self.root, bg=self.BG)
        outer.place(relx=0.5, rely=0.45, anchor=tk.CENTER)

        tk.Label(outer, text="Fitxer de cache carregat",
                 bg=self.BG, fg=self.FG,
                 font=("Segoe UI", 22, "bold")).pack(pady=(0, 30))

        # ── targeta d'informació ──────────────────────────────────────────────
        card = tk.Frame(outer, bg=self.BG3, padx=36, pady=28)
        card.pack(fill=tk.X)

        def info_row(label, value, value_color=None):
            row = tk.Frame(card, bg=self.BG3)
            row.pack(fill=tk.X, pady=6)
            tk.Label(row, text=label,
                     bg=self.BG3, fg=self.FG3,
                     font=("Segoe UI", 11),
                     width=24, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value,
                     bg=self.BG3, fg=value_color or self.FG,
                     font=("Segoe UI", 11, "bold"),
                     anchor="w").pack(side=tk.LEFT)

        info_row("Directori:",       directori)
        info_row("Últim escaneig:",  ultim_escaneig)
        info_row("Total fitxers:",   str(num_fitxers))

        dup_color = self.RED if num_pairs else self.GREEN
        info_row("Grups de duplicats:", str(num_grups), dup_color)
        info_row("Comparacions previstes:", str(num_pairs), dup_color)
        if self.missing_count:
            info_row("Descartats (no trobats al disc):",
                      str(self.missing_count), self.ORANGE)

        # ── botons ────────────────────────────────────────────────────────────
        btn_row = tk.Frame(outer, bg=self.BG)
        btn_row.pack(pady=40)

        if num_pairs:
            tk.Button(btn_row, text="Continuar  →",
                      command=self._start_review,
                      bg=self.GREEN, fg="white",
                      font=("Segoe UI", 13, "bold"),
                      padx=28, pady=12,
                      relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=12)
        else:
            tk.Label(outer,
                     text="✔  No s'han trobat fitxers duplicats.",
                     bg=self.BG, fg=self.GREEN,
                     font=("Segoe UI", 13)).pack(pady=(0, 20))

        tk.Button(btn_row, text="Sortir",
                  command=self.root.destroy,
                  bg=self.RED, fg="white",
                  font=("Segoe UI", 12),
                  padx=22, pady=12,
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=12)

        self._center_window()

    # ── inici de la revisió ───────────────────────────────────────────────────

    def _start_review(self):
        self.group_idx = 0
        self.current_files = []
        self.survivor = None
        self.cand_idx = None
        self.deleted = 0
        self.skipped = 0
        self.deleted_files = set()
        self._build_review_ui()
        self.root.after(120, self._show_current_pair)

    # ── construcció de la interfície de revisió ───────────────────────────────

    def _build_review_ui(self):
        self._clear()
        self.root.configure(bg=self.BG)

        # ── barra superior ────────────────────────────────────────────────────
        top = tk.Frame(self.root, bg=self.BG3, height=46)
        top.pack(fill=tk.X, side=tk.TOP)
        top.pack_propagate(False)

        self.title_var = tk.StringVar()
        tk.Label(top, textvariable=self.title_var,
                 bg=self.BG3, fg=self.FG,
                 font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT, padx=16, pady=12)

        self.stats_var = tk.StringVar()
        tk.Label(top, textvariable=self.stats_var,
                 bg=self.BG3, fg=self.FG3,
                 font=("Segoe UI", 10)).pack(side=tk.RIGHT, padx=16, pady=12)

        # ── barra de checksum ─────────────────────────────────────────────────
        self.chk_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.chk_var,
                 bg=self.BG4, fg="#505050",
                 font=("Courier New", 8),
                 anchor="w", padx=8, pady=3).pack(fill=tk.X, side=tk.TOP)

        # ── panells esquerra / dreta ──────────────────────────────────────────
        pane = tk.Frame(self.root, bg=self.BG)
        pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))

        # Esquerra
        left_outer = tk.Frame(pane, bg=self.BG2, bd=1, relief=tk.SUNKEN)
        left_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.left_info = tk.Label(left_outer, text="",
                                   bg=self.BG2, fg=self.FG2,
                                   font=("Segoe UI", 9),
                                   wraplength=580, justify=tk.LEFT,
                                   anchor="nw", padx=10, pady=8)
        self.left_info.pack(fill=tk.X)

        self.left_canvas = tk.Canvas(left_outer, bg="#111111",
                                      highlightthickness=0)
        self.left_canvas.pack(fill=tk.BOTH, expand=True)

        # Separador
        tk.Frame(pane, bg="#383838", width=3).pack(side=tk.LEFT, fill=tk.Y, padx=2)

        # Dreta
        right_outer = tk.Frame(pane, bg=self.BG2, bd=1, relief=tk.SUNKEN)
        right_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.right_info = tk.Label(right_outer, text="",
                                    bg=self.BG2, fg=self.FG2,
                                    font=("Segoe UI", 9),
                                    wraplength=580, justify=tk.LEFT,
                                    anchor="nw", padx=10, pady=8)
        self.right_info.pack(fill=tk.X)

        self.right_canvas = tk.Canvas(right_outer, bg="#111111",
                                       highlightthickness=0)
        self.right_canvas.pack(fill=tk.BOTH, expand=True)

        # ── barra de botons ───────────────────────────────────────────────────
        btn_bar = tk.Frame(self.root, bg=self.BG4)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=8, pady=8)

        btn_kw = dict(font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
                      cursor="hand2", padx=16, pady=9)

        self.btn_del_left = tk.Button(
            btn_bar, text="🗑  Eliminar ESQUERRA",
            command=lambda: self._delete_file("left"),
            bg=self.RED, fg="white", **btn_kw)
        self.btn_del_left.pack(side=tk.LEFT, padx=5)

        self.btn_del_right = tk.Button(
            btn_bar, text="🗑  Eliminar DRETA",
            command=lambda: self._delete_file("right"),
            bg=self.RED, fg="white", **btn_kw)
        self.btn_del_right.pack(side=tk.LEFT, padx=5)

        tk.Button(btn_bar, text="⏭  Saltar",
                  command=self._skip,
                  bg=self.GRAY, fg="white", **btn_kw).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_bar, text="✖  Finalitzar",
                  command=self._quit_review,
                  bg=self.ORANGE, fg="white", **btn_kw).pack(side=tk.RIGHT, padx=5)

    # ── mostrar la parella actual ─────────────────────────────────────────────

    def _enter_current_group(self):
        """Inicialitza l'estat de comparació pel grup group_idx: el
        supervivent és el primer fitxer i el candidat és el segon."""
        chk, files = self.groups[self.group_idx]
        self.current_chk = chk
        self.current_files = files
        self.survivor = files[0]
        self.cand_idx = 1

    def _advance_to_pending(self):
        """Passa al següent grup mentre l'actual estigui esgotat (cand_idx
        més enllà de l'últim fitxer). Retorna False quan no queda cap
        comparació pendent enlloc."""
        while self.group_idx < len(self.groups):
            if self.cand_idx is None:
                self._enter_current_group()
            if self.cand_idx < len(self.current_files):
                return True
            self.group_idx += 1
            self.cand_idx = None
        return False

    def _remaining_count(self):
        """Comparacions pendents: les que queden en el grup actual més
        les de tots els grups posteriors."""
        remaining = len(self.current_files) - self.cand_idx
        for _, files in self.groups[self.group_idx + 1:]:
            remaining += len(files) - 1
        return remaining

    def _show_current_pair(self):
        if not self._advance_to_pending():
            messagebox.showinfo(
                "Revisió completada",
                f"S'han revisat tots els grups de duplicats.\n\n"
                f"Eliminats: {self.deleted}\n"
                f"Saltats:   {self.skipped}",
                parent=self.root,
            )
            self.root.destroy()
            return

        left_rel  = self.survivor
        right_rel = self.current_files[self.cand_idx]
        remaining = self._remaining_count()

        self.title_var.set(
            f"Grup {self.group_idx + 1} / {len(self.groups)}"
            f"   ·   en queden {remaining}"
        )
        self.stats_var.set(
            f"Eliminats: {self.deleted}   |   Saltats: {self.skipped}"
        )
        self.chk_var.set(f"SHA-256: {self.current_chk}")

        self._populate_side("left",  left_rel)
        self._populate_side("right", right_rel)

    def _populate_side(self, side, rel_path):
        full_path = self.root_dir / rel_path
        info      = self.cache_data.get("fitxers", {}).get(rel_path, {})

        mida_str = format_size(info.get("mida", 0))
        dt_str   = format_mtime(info.get("mtime", 0))
        exists   = full_path.exists()
        warn     = "   ⚠ FITXER NO TROBAT AL DISC" if not exists else ""

        text = (
            f"Directori:  {full_path.parent}{warn}\n"
            f"Fitxer:  {full_path.name}   ·   {mida_str}   ·   {dt_str}"
        )

        if side == "left":
            self.left_info.config(
                text=text,
                fg="#e74c3c" if not exists else self.FG2,
            )
            canvas  = self.left_canvas
            img_idx = 0
        else:
            self.right_info.config(
                text=text,
                fg="#e74c3c" if not exists else self.FG2,
            )
            canvas  = self.right_canvas
            img_idx = 1

        canvas.delete("all")
        if exists:
            self.root.after(
                80,
                lambda c=canvas, p=full_path, i=img_idx:
                    self._draw_on_canvas(c, p, i)
            )
        else:
            canvas.after(
                10,
                lambda c=canvas: c.create_text(
                    max(c.winfo_width(), 200) // 2,
                    max(c.winfo_height(), 200) // 2,
                    text="⚠  Fitxer no trobat al disc",
                    fill="#e74c3c",
                    font=("Segoe UI", 13),
                    justify=tk.CENTER,
                )
            )

    def _draw_on_canvas(self, canvas, path, img_idx):
        """Dibuixa la previsualització al canvas indicat."""
        canvas.delete("all")
        w   = max(canvas.winfo_width(),  200)
        h   = max(canvas.winfo_height(), 200)
        ext = path.suffix.lower()

        if ext in IMAGE_EXTS:
            if not HAS_PIL:
                canvas.create_text(
                    w // 2, h // 2,
                    text="Per veure imatges cal Pillow:\npip install Pillow",
                    fill="#888888", justify=tk.CENTER,
                    font=("Segoe UI", 11))
                return
            try:
                img = Image.open(path)
                img.thumbnail((w, h), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._img_refs[img_idx] = photo   # evita GC
                canvas.create_image(w // 2, h // 2,
                                    anchor=tk.CENTER, image=photo)
            except Exception as exc:
                canvas.create_text(
                    w // 2, h // 2,
                    text=f"Error en carregar la imatge:\n{exc}",
                    fill="#888888", justify=tk.CENTER)

        elif ext in VIDEO_EXTS:
            canvas.create_text(
                w // 2, h // 2 - 20,
                text="🎬",
                fill="#aaaaaa", font=("Segoe UI", 36))
            canvas.create_text(
                w // 2, h // 2 + 28,
                text=f"Vídeo  ·  {path.name}",
                fill="#aaaaaa", justify=tk.CENTER,
                font=("Segoe UI", 11))
        else:
            canvas.create_text(
                w // 2, h // 2,
                text=f"📄  {path.name}\n\n(format no suportat)",
                fill="#888888", justify=tk.CENTER,
                font=("Segoe UI", 11))

    # ── accions ───────────────────────────────────────────────────────────────

    def _delete_file(self, side):
        left_rel  = self.survivor
        right_rel = self.current_files[self.cand_idx]
        rel_path  = left_rel  if side == "left" else right_rel
        full_path = self.root_dir / rel_path

        if not full_path.exists():
            messagebox.showerror(
                "Error", f"El fitxer no existeix al disc:\n{full_path}",
                parent=self.root)
            return

        if not messagebox.askyesno(
            "Confirmar eliminació",
            f"Esteu segur que voleu eliminar aquest fitxer?\n\n{full_path}",
            parent=self.root,
        ):
            return

        try:
            full_path.unlink()
            self.deleted += 1
            self.deleted_files.add(rel_path)
            if side == "left":
                # El candidat actual passa a ser el nou supervivent;
                # es continuarà comparant amb el següent del mateix grup.
                self.survivor = right_rel
            # Tant si s'ha eliminat l'esquerra com la dreta, avancem
            # al següent candidat del mateix grup (el supervivent es
            # manté fins que s'esgoti el grup).
            self.cand_idx += 1
            self._show_current_pair()
        except OSError as exc:
            messagebox.showerror("Error en eliminar", str(exc), parent=self.root)

    def _skip(self):
        self.skipped += 1
        self.cand_idx += 1
        self._show_current_pair()

    def _quit_review(self):
        if messagebox.askyesno(
            "Finalitzar la revisió",
            f"Voleu finalitzar la revisió?\n\n"
            f"Eliminats: {self.deleted}\n"
            f"Saltats:   {self.skipped}",
            parent=self.root,
        ):
            self.root.destroy()


# ── punt d'entrada ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cache_arg = sys.argv[1] if len(sys.argv) > 1 else None
    DuplicatsApp(cache_arg)

from __future__ import annotations

from pathlib import Path

import tkinter as tk
from tkinter import messagebox

from ..core.review_ops import move_similar_files
from ..core.similarity import find_similar, is_image

THUMB = 220
BG = "#1e1e1e"


def open_photo_viewer(parent, path: Path, title: str) -> None:
    from PIL import Image, ImageOps, ImageTk

    win = tk.Toplevel(parent)
    win.title(title)
    win.configure(bg="#111111")
    try:
        win.state("zoomed")
    except tk.TclError:
        win.geometry(f"{win.winfo_screenwidth()}x{win.winfo_screenheight()}+0+0")
    canvas = tk.Canvas(win, bg="#111111", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)
    with Image.open(path) as im:
        original = ImageOps.exif_transpose(im).convert("RGB")
    ref = [None]

    def render(_event=None):
        w, h = max(canvas.winfo_width(), 50), max(canvas.winfo_height(), 50)
        img = original.copy()
        img.thumbnail((w, h), Image.LANCZOS)
        ref[0] = ImageTk.PhotoImage(img)
        canvas.delete("all")
        canvas.create_image(w // 2, h // 2, image=ref[0])

    canvas.bind("<Configure>", render)
    win.bind("<Escape>", lambda _e: win.destroy())
    canvas.bind("<Button-1>", lambda _e: win.destroy())
    win.focus_set()


def show_similar_photos(parent, reference: Path, missing_files, source_root: Path, dest_dir: Path, state) -> list[Path]:
    """Cerca fotos semblants a `reference` entre les pendents i deixa moure les triades a `dest_dir`."""
    try:
        from PIL import Image, ImageOps, ImageTk
    except ImportError:
        return []
    if not is_image(reference):
        return []

    pending = {}
    for entry in missing_files[state.idx:]:
        rel = Path(entry[0])
        full = source_root / rel
        if is_image(full) and full.is_file():
            pending[full] = rel
    if not pending:
        return []

    parent.config(cursor="watch")
    parent.update_idletasks()
    try:
        matches = find_similar(reference, list(pending))
    except Exception as e:
        messagebox.showwarning("Fotos semblants", f"No s'ha pogut fer la cerca: {e}", parent=parent)
        return []
    finally:
        parent.config(cursor="")
    if not matches:
        return []

    dlg = tk.Toplevel(parent)
    dlg.title(f"Fotos semblants a {reference.name}")
    dlg.configure(bg=BG)
    screen_w = dlg.winfo_screenwidth()
    screen_h = dlg.winfo_screenheight()
    window_w = min(1400, screen_w - 40)
    window_h = min(900, screen_h - 120)
    dlg.geometry(
        f"{window_w}x{window_h}+{(screen_w - window_w) // 2}+{max(0, (screen_h - window_h - 48) // 2)}"
    )
    dlg.minsize(min(760, window_w), min(500, window_h))
    dlg.grid_columnconfigure(0, weight=1)
    dlg.grid_rowconfigure(1, weight=1)
    dlg.transient(parent)

    tk.Label(
        dlg,
        text=f"S'han trobat {len(matches)} foto(s) semblants. Clic a la imatge per ampliar-la; marca les que vulguis moure a:\n{dest_dir}",
        bg=BG, fg="#dddddd", font=("Segoe UI", 10), justify=tk.LEFT,
    ).grid(row=0, column=0, sticky="ew", padx=10, pady=8)

    body = tk.Frame(dlg, bg=BG)
    body.grid(row=1, column=0, sticky="nsew", padx=10)
    canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
    scroll = tk.Scrollbar(body, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    grid = tk.Frame(canvas, bg=BG)
    grid_window = canvas.create_window((0, 0), window=grid, anchor="nw")
    grid.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(grid_window, width=e.width))
    canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120 or 1), "units"))
    canvas.bind("<Button-4>", lambda _e: canvas.yview_scroll(-3, "units"))
    canvas.bind("<Button-5>", lambda _e: canvas.yview_scroll(3, "units"))

    thumbs = []
    checks = []
    moved_paths = []

    def add_cell(index, path, caption, selectable, rel=None):
        cell = tk.Frame(grid, bg="#2a2f38", padx=6, pady=6)
        cell.grid(row=index // 4, column=index % 4, padx=6, pady=6)
        try:
            with Image.open(path) as im:
                img = ImageOps.exif_transpose(im).convert("RGB")
            img.thumbnail((THUMB, THUMB), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
        except Exception:
            photo = None
        thumbs.append(photo)
        lbl = tk.Label(cell, image=photo, text="" if photo else "[error]", bg="#111111", cursor="hand2")
        lbl.pack()
        lbl.bind("<Button-1>", lambda _e, p=path: open_photo_viewer(dlg, p, p.name))
        tk.Label(cell, text=caption, bg="#2a2f38", fg="#e8eef6", font=("Segoe UI", 8), wraplength=THUMB).pack()
        if selectable:
            var = tk.BooleanVar(value=False)
            var.trace_add("write", lambda *_a: update_count())
            tk.Checkbutton(
                cell, text="Mou aquesta foto", variable=var, bg="#2a2f38", fg="#ffffff",
                selectcolor="#26734d", activebackground="#2a2f38",
                activeforeground="#ffffff", font=("Segoe UI", 10, "bold"),
                padx=8, pady=5, cursor="hand2",
            ).pack(fill=tk.X, pady=(4, 0))
            checks.append((var, rel))

    def update_count():
        move_btn.config(text=f"Mou seleccionades ({sum(1 for v, _ in checks if v.get())})")

    def set_all(value):
        for var, _ in checks:
            var.set(value)

    add_cell(0, reference, f"{reference.name}\n(foto moguda)", False)
    for i, m in enumerate(matches, start=1):
        note = f"{m.score:.2f}" + (f", {m.inliers} punts coincidents" if m.inliers else "")
        if not m.verified:
            note += ", sense verificar"
        add_cell(i, m.path, f"{m.path.name}\nsimilitud {note}", True, pending[m.path])

    def move_selected():
        rels = [rel for var, rel in checks if var.get()]
        if not rels:
            dlg.destroy()
            return
        moved, errors = move_similar_files(source_root, rels, dest_dir, state)
        moved_paths.extend(moved)
        moved_keys = {str(r) for r in moved}
        missing_files[:] = [e for e in missing_files if str(Path(e[0])) not in moved_keys]
        if errors:
            messagebox.showerror(
                "Error en moure", "\n".join(f"{r}: {msg}" for r, msg in errors), parent=dlg
            )
        dlg.destroy()

    btns = tk.Frame(dlg, bg="#30363f", height=68)
    btns.grid(row=2, column=0, sticky="ew", padx=10, pady=(6, 10))
    btns.grid_propagate(False)
    move_btn = tk.Button(btns, text="Mou seleccionades (0)", command=move_selected, bg="#4CAF50", fg="white",
                         font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2", height=2)
    move_btn.pack(side=tk.LEFT, padx=(8, 6), pady=8)
    tk.Button(btns, text="Marca tot", command=lambda: set_all(True), font=("Segoe UI", 10),
              relief=tk.FLAT, cursor="hand2", height=2).pack(side=tk.LEFT, padx=6, pady=8)
    tk.Button(btns, text="Deselecciona tot", command=lambda: set_all(False), font=("Segoe UI", 10),
              relief=tk.FLAT, cursor="hand2", height=2).pack(side=tk.LEFT, padx=6, pady=8)
    tk.Button(btns, text="Cancel·la", command=dlg.destroy, font=("Segoe UI", 10),
              relief=tk.FLAT, cursor="hand2", height=2).pack(side=tk.RIGHT, padx=8, pady=8)

    dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
    dlg.grab_set()
    parent.wait_window(dlg)
    return moved_paths

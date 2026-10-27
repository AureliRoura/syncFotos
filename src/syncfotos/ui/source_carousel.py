from __future__ import annotations

from pathlib import Path

import tkinter as tk

THUMB_WIDTH = 176
THUMB_HEIGHT = 112
MAX_VISIBLE_PHOTOS = 30
ROW_HEIGHT = 178


class SourcePhotoCarousel:
    def __init__(self, parent, photos: list[Path], on_open):
        self._all_photos = photos
        self._directory_photos = photos
        self._removed: set[Path] = set()
        self.photos = photos
        self.on_open = on_open
        self.directory: Path | None = None
        self.current: Path | None = None
        self.similar: set[Path] = set()
        self.selected: set[Path] = set()
        self.status = tk.StringVar(value="Preparat")
        self.selection_status = tk.StringVar(value="Marcades per moure amb l'actual: 0")
        self.only_similar = tk.BooleanVar(value=False)
        self.filter_text = tk.StringVar(value="Només fotos semblants (0)")
        self._images = []

        self.frame = tk.Frame(parent, bg="#1e1e1e", width=205)
        self.frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 6))
        self.frame.pack_propagate(False)
        tk.Label(
            self.frame, text="Fotos de l'origen", bg="#1e1e1e", fg="#dddddd",
            font=("Segoe UI", 10, "bold"), anchor="w",
        ).pack(fill=tk.X, pady=(2, 5))
        body = tk.Frame(self.frame, bg="#1e1e1e")
        body.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(body, width=THUMB_WIDTH + 12, bg="#111111", highlightthickness=0)
        scrollbar = tk.Scrollbar(body, orient=tk.VERTICAL, command=self._scroll)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._render())
        self.canvas.bind("<MouseWheel>", self._mousewheel)
        self.canvas.bind("<Button-4>", lambda _event: self._scroll_units(-3))
        self.canvas.bind("<Button-5>", lambda _event: self._scroll_units(3))
        tk.Checkbutton(
            self.frame, textvariable=self.filter_text, variable=self.only_similar,
            command=lambda: self._refresh_photos(reset_scroll=True),
            bg="#1e1e1e", fg="#dddddd", selectcolor="#111111",
            activebackground="#1e1e1e", activeforeground="#ffffff",
            font=("Segoe UI", 8), anchor="w",
        ).pack(fill=tk.X, pady=(5, 0))
        tk.Label(
            self.frame, textvariable=self.status, bg="#1e1e1e", fg="#aaaaaa",
            font=("Segoe UI", 8), anchor="w", wraplength=195,
        ).pack(fill=tk.X, pady=(5, 2))
        tk.Label(
            self.frame, textvariable=self.selection_status, bg="#1e1e1e", fg="#f0c674",
            font=("Segoe UI", 8), anchor="w", wraplength=195,
        ).pack(fill=tk.X, pady=(2, 2))
        self.canvas.configure(scrollregion=(0, 0, THUMB_WIDTH + 12, len(photos) * ROW_HEIGHT))

    def set_directory(self, directory: Path):
        directory = Path(directory).resolve()
        if self.directory is not None and directory != self.directory:
            self.selected.clear()
        self.directory = directory
        self._directory_photos = [
            path for path in self._all_photos
            if path.resolve().parent == self.directory and path.resolve() not in self._removed
        ]
        self._refresh_photos(reset_scroll=True)

    def set_ordered_photos(self, photos: list[Path]):
        self._all_photos = [path for path in photos if path.resolve() not in self._removed]
        available = {path.resolve() for path in self._all_photos}
        self.selected.intersection_update(available)
        if self.directory is not None:
            self._directory_photos = [
                path for path in self._all_photos if path.resolve().parent == self.directory
            ]
        else:
            self._directory_photos = list(self._all_photos)
        self._refresh_photos(reset_scroll=True)

    def selected_paths(self) -> list[Path]:
        return [path for path in self._directory_photos if path.resolve() in self.selected]

    def _toggle_selection(self, path: Path):
        key = path.resolve()
        if key == self.current:
            return
        if key in self.selected:
            self.selected.remove(key)
        else:
            self.selected.add(key)
        self.selection_status.set(
            f"Marcades per moure amb l'actual: {len(self.selected)}"
        )
        self._render()

    def set_current(self, current: Path):
        self.current = Path(current).resolve()
        self._refresh_photos(reset_scroll=True)

    def _refresh_photos(self, reset_scroll=False):
        current = [path for path in self._directory_photos if path.resolve() == self.current]
        matches = [
            path for path in self._directory_photos
            if path.resolve() in self.similar and path.resolve() != self.current
        ]
        self.filter_text.set(f"Només fotos semblants ({len(matches)})")
        rest = [path for path in self._directory_photos if path.resolve() != self.current]
        ordered = current + matches if self.only_similar.get() else current + rest
        self.photos = ordered[:MAX_VISIBLE_PHOTOS]
        if reset_scroll:
            self.canvas.yview_moveto(0)
        self.canvas.configure(scrollregion=(0, 0, THUMB_WIDTH + 12, len(self.photos) * ROW_HEIGHT))
        self._render()

    def _scroll(self, *args):
        self.canvas.yview(*args)
        self._render()

    def _scroll_units(self, count):
        self.canvas.yview_scroll(count, "units")
        self._render()

    def _mousewheel(self, event):
        self._scroll_units(-1 * (event.delta // 120 or 1))

    def set_results(self, current: Path | None, similar: set[Path], status: str):
        self.current = current.resolve() if current else None
        self.similar = {p.resolve() for p in similar}
        self.status.set(status)
        self._refresh_photos()

    def remove_paths(self, paths: set[Path]):
        removed = {p.resolve() for p in paths}
        self._removed.update(removed)
        self.selected.difference_update(removed)
        self.selection_status.set(
            f"Marcades per moure amb l'actual: {len(self.selected)}"
        )
        self._all_photos = [p for p in self._all_photos if p.resolve() not in removed]
        self._directory_photos = [p for p in self._directory_photos if p.resolve() not in removed]
        self._refresh_photos()

    def _render(self):
        if not self.canvas.winfo_exists():
            return
        self.canvas.delete("visible")
        self._images.clear()
        height = max(self.canvas.winfo_height(), ROW_HEIGHT)
        start = max(0, int(self.canvas.canvasy(0) // ROW_HEIGHT))
        end = min(len(self.photos), start + height // ROW_HEIGHT + 2)
        from PIL import Image, ImageOps, ImageTk

        width = max(self.canvas.winfo_width(), THUMB_WIDTH + 12)
        for index in range(start, end):
            path = self.photos[index]
            y = index * ROW_HEIGHT
            key = path.resolve()
            current = key == self.current
            similar = key in self.similar
            selected = key in self.selected
            outline = "#4f8cff" if current else "#f0c674" if selected else "#55c98a" if similar else "#454a52"
            self.canvas.create_rectangle(
                4, y + 3, width - 4, y + ROW_HEIGHT - 3,
                fill="#252a31", outline=outline, width=3 if current or similar or selected else 1,
                tags=("visible", f"photo_{index}"),
            )
            try:
                with Image.open(path) as source:
                    image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((THUMB_WIDTH, THUMB_HEIGHT), Image.LANCZOS)
                photo = ImageTk.PhotoImage(image)
            except Exception:
                photo = None
            if photo:
                self._images.append(photo)
                self.canvas.create_image(
                    width // 2, y + 5, anchor=tk.N, image=photo,
                    tags=("visible", f"photo_{index}"),
                )
            marker = "FOTO ACTUAL" if current else "SEMBLANT" if similar else ""
            if marker:
                self.canvas.create_text(
                    width // 2, y + 121, text=marker, fill=outline,
                    font=("Segoe UI", 8, "bold"), tags=("visible", f"photo_{index}"),
                )
            filename = path.name
            if len(filename) > 26:
                filename = filename[:23] + "..."
            self.canvas.create_text(
                width // 2, y + 137, text=filename, fill="#e8eef6",
                font=("Segoe UI", 8), tags=("visible", f"photo_{index}"),
            )
            if not current:
                select_tag = f"select_{index}"
                self.canvas.create_rectangle(
                    12, y + 151, 28, y + 167,
                    fill="#26734d" if selected else "#111111",
                    outline="#d9e2ec", width=1, tags=("visible", select_tag),
                )
                if selected:
                    self.canvas.create_text(
                        20, y + 159, text="✓", fill="white",
                        font=("Segoe UI", 9, "bold"), tags=("visible", select_tag),
                    )
                self.canvas.create_text(
                    34, y + 159, text="Mou amb l'actual", fill="#e8eef6",
                    font=("Segoe UI", 8), anchor="w", tags=("visible", select_tag),
                )
                self.canvas.tag_bind(
                    select_tag, "<Button-1>",
                    lambda _event, selected_path=path: self._toggle_selection(selected_path),
                )
            self.canvas.tag_bind(
                f"photo_{index}", "<Button-1>",
                lambda _event, selected=path: self.on_open(selected),
            )
#!/usr/bin/env python3
from __future__ import annotations

import queue
import subprocess
import sys
import threading
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


WINDOW_BG = "#1f232a"
PANEL_BG = "#2a2f38"
ENTRY_BG = "#ffffff"
TEXT_BG = "#111418"
TEXT_FG = "#e8eef6"
ACCENT = "#4f8cff"
ACCENT_2 = "#2ecc71"
DANGER = "#c0392b"
MUTED = "#b7c0cc"


def launch_sync_fotos_gui(script_path: Path) -> None:
    script_path = script_path.resolve()
    root = tk.Tk()
    root.title("SyncFotos")
    root.configure(bg=WINDOW_BG)
    root.geometry("860x640")
    root.minsize(820, 600)

    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except tk.TclError:
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

    style.configure("TFrame", background=WINDOW_BG)
    style.configure("Panel.TFrame", background=PANEL_BG)
    style.configure("TLabel", background=WINDOW_BG, foreground=TEXT_FG)
    style.configure("Title.TLabel", background=WINDOW_BG, foreground=TEXT_FG, font=("Segoe UI", 16, "bold"))
    style.configure("Hint.TLabel", background=WINDOW_BG, foreground=MUTED)
    style.configure("TCheckbutton", background=WINDOW_BG, foreground=TEXT_FG)
    style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    fields = {}
    status_var = tk.StringVar(value="Emplena els camps i prem Executa.")
    run_button = None
    log_queue: queue.Queue[str | None] = queue.Queue()
    worker: threading.Thread | None = None

    def add_field(row: int, label: str, default: str = "", browse: str | None = "dir") -> tk.Entry:
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=7)
        entry = tk.Entry(form, bg=ENTRY_BG, relief=tk.FLAT, highlightthickness=1, highlightbackground="#6c7786")
        entry.insert(0, default)
        entry.grid(row=row, column=1, sticky="ew", pady=7)
        fields[label] = entry

        if browse:
            def pick_path() -> None:
                if browse == "dir":
                    chosen = filedialog.askdirectory(parent=root)
                else:
                    chosen = filedialog.asksaveasfilename(parent=root)
                if chosen:
                    entry.delete(0, tk.END)
                    entry.insert(0, chosen)

            ttk.Button(form, text="Explora", command=pick_path).grid(row=row, column=2, padx=(10, 0), pady=7)

        return entry

    def append_log(text: str) -> None:
        output.configure(state=tk.NORMAL)
        output.insert(tk.END, text)
        output.see(tk.END)
        output.configure(state=tk.DISABLED)

    def set_running(running: bool) -> None:
        nonlocal run_button
        state = tk.DISABLED if running else tk.NORMAL
        for widget in inputs_to_toggle:
            widget.configure(state=state)
        run_button.configure(state=state)
        status_var.set("Executant..." if running else "Executat.")

    def build_command() -> list[str]:
        origen = fields["Origen"].get().strip()
        desti = fields["Desti"].get().strip()
        cache_dir = fields["Cache dir"].get().strip()
        sortida = fields["Sortida"].get().strip()
        script_eliminacio = fields["Script eliminacio"].get().strip()

        if not origen or not desti:
            raise ValueError("Has d'indicar origen i desti.")

        command = [sys.executable, str(script_path), origen, desti]
        if options["generar_sortida"].get():
            command.append("--generar-sortida")
        if options["mostrar_checksum"].get():
            command.append("--mostrar-checksum")
        if sortida:
            command.extend(["--sortida", sortida])
        if cache_dir:
            command.extend(["--cache-dir", cache_dir])
        if options["netejar_cache_origen"].get():
            command.append("--netejar-cache-origen")
        if script_eliminacio:
            command.extend(["--script-eliminacio", script_eliminacio])
        if options["revisar"].get():
            command.append("--revisar")
        return command

    def run_script() -> None:
        try:
            command = build_command()
        except ValueError as exc:
            messagebox.showerror("Falta informació", str(exc), parent=root)
            return

        output.configure(state=tk.NORMAL)
        output.delete("1.0", tk.END)
        output.configure(state=tk.DISABLED)
        append_log("Ordre executada:\n")
        append_log(" ".join(f'"{part}"' if " " in part else part for part in command) + "\n\n")

        set_running(True)

        def worker_main() -> None:
            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=str(script_path.parent),
                )
                assert process.stdout is not None
                for line in process.stdout:
                    log_queue.put(line)
                return_code = process.wait()
                log_queue.put(f"\n[sortida] Procés finalitzat amb codi {return_code}\n")
            except Exception as exc:  # pragma: no cover - surfaced in UI
                log_queue.put(f"\n[error] {exc}\n")
            finally:
                log_queue.put(None)

        threading.Thread(target=worker_main, daemon=True).start()

    def poll_logs() -> None:
        finished = False
        while True:
            try:
                item = log_queue.get_nowait()
            except queue.Empty:
                break
            if item is None:
                finished = True
            else:
                append_log(item)
        if finished:
            set_running(False)
            status_var.set("Finalitzat. Revisa la sortida anterior si cal.")
            return
        root.after(80, poll_logs)

    header = ttk.Frame(root)
    header.pack(fill=tk.X, padx=20, pady=(18, 10))
    ttk.Label(header, text="SyncFotos", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        header,
        text="Carrega els camins i opcions quan el programa es llanci sense arguments.",
        style="Hint.TLabel",
    ).pack(anchor="w", pady=(4, 0))

    form_panel = ttk.Frame(root, style="Panel.TFrame")
    form_panel.pack(fill=tk.X, padx=20, pady=(0, 12))

    form = ttk.Frame(form_panel)
    form.pack(fill=tk.X, padx=16, pady=16)
    form.columnconfigure(1, weight=1)

    add_field(0, "Origen")
    add_field(1, "Desti")
    add_field(2, "Cache dir", default=str((Path.cwd() / "cache")))
    add_field(3, "Sortida", browse="file")
    add_field(4, "Script eliminacio", browse="file")

    options = {
        "generar_sortida": tk.BooleanVar(value=False),
        "mostrar_checksum": tk.BooleanVar(value=False),
        "netejar_cache_origen": tk.BooleanVar(value=False),
        "revisar": tk.BooleanVar(value=True),
    }

    options_row = ttk.Frame(root)
    options_row.pack(fill=tk.X, padx=20, pady=(0, 10))
    ttk.Checkbutton(options_row, text="Generar sortida", variable=options["generar_sortida"]).pack(anchor="w")
    ttk.Checkbutton(options_row, text="Mostrar checksum", variable=options["mostrar_checksum"]).pack(anchor="w")
    ttk.Checkbutton(options_row, text="Netejar cache origen", variable=options["netejar_cache_origen"]).pack(anchor="w")
    ttk.Checkbutton(options_row, text="Revisar fitxers mancants", variable=options["revisar"]).pack(anchor="w")

    button_row = ttk.Frame(root)
    button_row.pack(fill=tk.X, padx=20, pady=(4, 8))

    inputs_to_toggle = [
        fields["Origen"],
        fields["Desti"],
        fields["Cache dir"],
        fields["Sortida"],
        fields["Script eliminacio"],
    ]

    run_button = ttk.Button(button_row, text="Executa", style="Accent.TButton", command=run_script)
    run_button.pack(side=tk.LEFT)
    ttk.Button(button_row, text="Sortir", command=root.destroy).pack(side=tk.LEFT, padx=(10, 0))
    ttk.Label(button_row, textvariable=status_var, style="Hint.TLabel").pack(side=tk.RIGHT)

    log_panel = ttk.Frame(root, style="Panel.TFrame")
    log_panel.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
    output = tk.Text(
        log_panel,
        bg=TEXT_BG,
        fg=TEXT_FG,
        insertbackground=TEXT_FG,
        relief=tk.FLAT,
        wrap=tk.WORD,
        font=("Consolas", 10),
    )
    output.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
    output.insert(tk.END, "La sortida del programa apareixerà aquí.\n")
    output.configure(state=tk.DISABLED)

    root.after(80, poll_logs)
    root.mainloop()


if __name__ == "__main__":
    launch_sync_fotos_gui(Path(__file__).resolve().parents[3] / "sync_fotos.py")

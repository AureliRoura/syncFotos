#!/usr/bin/env python3
import argparse
import hashlib
import json
import shutil
import sys
import re
from datetime import datetime
from pathlib import Path


import platform


_video_ref = [None]
seeking = False
seek_job = None
seek_after = None
dragging = False
has_paused = False

BLOCK_SIZE = 65536

def compute_checksum(path):
    sha256 = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(BLOCK_SIZE):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, PermissionError) as e:
        print(f"[AVIS] No es pot llegir '{path}': {e}", file=sys.stderr)
        return None

def count_files(directory):
    return sum(1 for p in directory.rglob("*") if p.is_file())

def cache_path_for(directory, cache_dir):
    dir_hash = hashlib.md5(str(directory).encode()).hexdigest()[:8]
    safe_name = directory.name[:30].replace(" ", "_")
    return cache_dir / f"cache_{safe_name}_{dir_hash}.json"

def load_cache(cache_file):
    if not cache_file.exists():
        return {}
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[AVIS] No s ha pogut carregar la cache '{cache_file}': {e}", file=sys.stderr)
        return {}

def save_cache(cache_file, data):
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[AVIS] No s ha pogut desar la cache '{cache_file}': {e}", file=sys.stderr)

def scan_directory(directory, total, cache_data):
    cached_files = cache_data.get("fitxers", {})
    new_files = {}
    result = {}
    processed = 0
    reused = 0

    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue
        rel = str(file_path.relative_to(directory))
        try:
            stat = file_path.stat()
            mtime = stat.st_mtime
            size = stat.st_size
        except OSError:
            processed += 1
            continue

        cached = cached_files.get(rel)
        if cached and cached.get("mtime") == mtime and cached.get("mida") == size:
            checksum = cached["checksum"]
            reused += 1
        else:
            checksum = compute_checksum(file_path)
            if checksum is None:
                processed += 1
                continue

        new_files[rel] = {"checksum": checksum, "mtime": mtime, "mida": size}
        result[rel] = checksum
        processed += 1
        pct = processed * 100 // total if total else 100
        print(f"\r  {processed}/{total} fitxers ({pct}%) [{reused} de cache]   ", end="", file=sys.stderr)

    print(file=sys.stderr)
    updated_cache = {
        "directori": str(directory),
        "ultim_escaneig": datetime.now().isoformat(timespec="seconds"),
        "fitxers": new_files,
    }
    return result, updated_cache

def data_a_path(filename):
    filename = Path(filename).name
    match = re.search(r'_(\d{8})_', filename)
    if not match:
        return None

    data = datetime.strptime(match.group(1), "%Y%m%d")

    return Path(str(data.year)) / f"{data.year}_{data.month:02d}_{data.day:02d}"

def revisar_fitxers(missing_files, source_root, target_root):
    """
    Mostra les fotos mancants una a una i permet moure-les a un directori triat.
    Requereix: tkinter (stdlib). Pillow (pip install Pillow) per previsualitzar.
    """
    import tkinter as tk
    from tkinter import filedialog, messagebox

    try:
        from PIL import Image, ImageTk
        HAS_PIL = True
    except ImportError:
        HAS_PIL = False
        print("[AVIS] Pillow no instal·lat; no es mostraran imatges.", file=sys.stderr)
        print("       Instal·leu-lo amb: pip install Pillow", file=sys.stderr)

    try:
        import vlc
    
    except ImportError:
        print("[AVIS] VLC no instal·lat; no es podran reproduir vídeos.", file=sys.stderr)
        print("       Instal·leu-lo amb: pip install python-vlc", file=sys.stderr)
        vlc = None

    vlc_instance = vlc.Instance()
    player = vlc_instance.media_player_new()

    total = len(missing_files)
    state = {"idx": 0, "last_dir": target_root, "mogudes": 0, "saltades": 0}


    def center_window(window):
        window.update_idletasks()
    
        width = window.winfo_width()
        height = window.winfo_height()
    
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
    
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
    
        window.geometry(f"+{x}+{y}")
    
    def on_slider_press(event):
        global dragging
        dragging = True

    def on_slider_release(event):
        global dragging
        dragging = False
        player.set_position(video_pos.get() / 1000.0)

    def on_press(event):
        global dragging, has_paused
        dragging = True
        if player.is_playing():
            player.pause()
            while player.get_state() != vlc.State.Paused:
                pass
            has_paused = True

    def on_release(event):
        global dragging, has_paused
        dragging = False
        player.set_position(video_pos.get() / 1000.0)
        if has_paused:
            player.play()
            has_paused = False

    def toggle_play():
            player.pause()
    
    def seek_video(value):
        if dragging:
            player.set_position(float(value) / 1000.0)


    def update_video_position():
        if player.is_playing() and not dragging:
            pos = player.get_position()
            if pos >= 0:
                video_pos.set(int(pos * 1000))

        root.after(250, update_video_position)

    root = tk.Tk()
    root.title("Revisar fotos mancants")
    root.geometry("960x740")
    root.configure(bg="#1e1e1e")

    # Info bar
    info_var = tk.StringVar()
    tk.Label(root, textvariable=info_var, bg="#1e1e1e", fg="#dddddd",
             font=("Segoe UI", 10), anchor="w", wraplength=940).pack(
        fill=tk.X, padx=10, pady=(10, 4))

    # Canvas imatge
    # canvas = tk.Canvas(root, bg="#111111", highlightthickness=0)
    # canvas.pack(expand=True, fill=tk.BOTH, padx=10)
    _img_ref = [None]  # evita GC de la imatge

    # Frame video
    viewer = tk.Frame(root)
    viewer.pack(expand=True, fill=tk.BOTH, padx=10)
    canvas = tk.Canvas(viewer, bg="#111111", highlightthickness=0)
    canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

    video_frame = tk.Frame(viewer, bg="#111111")
    video_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
    video_frame.lower()  # inicialment amagat
    video_controls = tk.Frame(root)
    play_btn = tk.Button(video_controls, text="▶ / ❚❚", command=toggle_play)
    play_btn.pack(side=tk.LEFT)

    video_pos = tk.Scale(
        video_controls,
        orient=tk.HORIZONTAL,
        from_=0,
        to=1000,
        showvalue=False,
        command=seek_video,
    )
    video_pos.bind("<ButtonPress-1>", on_press)
    video_pos.bind("<ButtonRelease-1>", on_release)
    video_pos.pack(side=tk.LEFT, fill=tk.X, expand=True)
    video_controls.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 5))
    

    # Barra botons
    btn_frame = tk.Frame(root, bg="#1e1e1e")
    btn_frame.pack(fill=tk.X, padx=10, pady=8)

    stats_var = tk.StringVar()
    tk.Label(btn_frame, textvariable=stats_var, bg="#1e1e1e", fg="#aaaaaa",
             font=("Segoe UI", 9)).pack(side=tk.RIGHT, padx=12)

    update_video_position()
    center_window(root)

    def add_tooltip(widget, text_func):
        tip = None
    
        def enter(event):
            nonlocal tip
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
    
            lbl = tk.Label(
                tip,
                text=text_func(),
                bg="#ffffe0",
                relief="solid",
                borderwidth=1,
                padx=5,
                pady=2,
                justify=tk.LEFT,
            )
            lbl.pack()
    
        def leave(event):
            nonlocal tip
            if tip:
                tip.destroy()
                tip = None
    
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)


    def update_stats():
        stats_var.set(f"Mogudes: {state['mogudes']}  |  Saltades: {state['saltades']}")

    def load_video(path):

        if vlc is None:
            print("[AVIS] VLC no disponible; no es pot reproduir el video.", file=sys.stderr)
            return
        if not video_controls.winfo_ismapped():
            video_controls.pack(before=btn_frame, fill=tk.X, padx=10, pady=(0, 5))
        if player.is_playing():
            player.stop()
            player.set_media(None)
        video_frame.lift()
        video_frame.update()
        wid = video_frame.winfo_id()
        media = vlc_instance.media_new(str(path))
        player.set_media(media)
    
        # És important que el Frame ja tingui un identificador nadiu
    
        player.set_hwnd(wid)
        player.set_xwindow(wid)
        if platform.system() == "Windows":
            player.set_hwnd(wid)
        elif platform.system() == "Linux":
            player.set_nsobject(wid)
        elif platform.system() == "Darwin":
            player.set_nsobject(wid)

        player.play()

    def load_img(path):
        if player.is_playing():
            player.stop()
            player.set_media(None)
        video_controls.pack_forget()
        video_frame.lower()
        canvas.delete("all")
        cw = max(canvas.winfo_width(), 200)
        ch = max(canvas.winfo_height(), 200)
        if not HAS_PIL:
            canvas.create_text(cw // 2, ch // 2,
                               text="[Instal·leu Pillow per veure la imatge]\npip install Pillow",
                               fill="#888888", justify=tk.CENTER)
            return
        try:
            img = Image.open(path)
            img.thumbnail((cw, ch), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            _img_ref[0] = photo
            canvas.create_image(cw // 2, ch // 2, anchor=tk.CENTER, image=photo)
        except Exception as e:
            canvas.create_text(cw // 2, ch // 2,
                               text=f"[No es pot mostrar]\n{e}",
                               fill="#888888", justify=tk.CENTER)

    def show_current():
        if state["idx"] >= total:
            messagebox.showinfo(
                "Revisio completada",
                f"S'han revisat tots els fitxers.\n\nMogudes: {state['mogudes']}\nSaltades: {state['saltades']}"
            )
            root.destroy()
            return
        if data_a_path(missing_files[state["idx"]][0]) is None:
            btn_from_file.config(state=tk.DISABLED)
        else:
            btn_from_file.config(state=tk.NORMAL)
        rel_path, _ = missing_files[state["idx"]]
        full_path = source_root / rel_path
        root.title(f"Revisar fotos mancants  ({state['idx'] + 1}/{total})")
        info_var.set(f"{state['idx'] + 1} / {total}   \u2192   {rel_path}")
        update_stats()

        ext = full_path.suffix.lower()
    
        if ext in {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}:
            root.after(30, lambda: load_img(full_path))
        elif ext in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
            root.after(30, lambda: load_video(full_path))
        else:
            print(f"Format no suportat: {full_path}")


    def move_file():
        chosen = filedialog.askdirectory(
            title="Selecciona on moure el fitxer",
            initialdir=str(state["last_dir"]),
            parent=root,
        )
        if chosen:
            move_file_to(Path(chosen))
    
    
    def move_file_to(dest_dir: Path):
        rel_path, _ = missing_files[state["idx"]]
        full_path = source_root / rel_path
    
        dest_dir.mkdir(parents=True, exist_ok=True)
    
        dest_file = dest_dir / full_path.name
        if dest_file.exists():
            stem, suffix, i = full_path.stem, full_path.suffix, 1
            while dest_file.exists():
                dest_file = dest_dir / f"{stem}_{i}{suffix}"
                i += 1
    
        try:
            shutil.move(str(full_path), dest_file)
            state["last_dir"] = dest_dir
            state["mogudes"] += 1
            state["idx"] += 1
            show_current()
            state["last_dir"] = dest_dir
        except OSError as e:
            messagebox.showerror("Error en moure", str(e))

    def skip_file():
        state["saltades"] += 1
        state["idx"] += 1
        show_current()

    def quit_review():
        if messagebox.askyesno(
            "Sortir",
            f"Sortir de la revisio?\n\nMogudes: {state['mogudes']}\nSaltades: {state['saltades']}"
        ):
            root.destroy()

    btn_last = tk.Button(
        btn_frame,
        text="Mou últim",
        command=lambda: move_file_to(state["last_dir"]),
        width=14,
        bg="#2E86C1",
        fg="white",
        font=("Segoe UI", 10, "bold"),
        relief=tk.FLAT,
        cursor="hand2"
    )
    btn_last.pack(side=tk.LEFT, padx=4)

    add_tooltip(
        btn_last,
        lambda: f"Últim directori:\n{state['last_dir']}"
    )

    btn_from_file = tk.Button(
        btn_frame,
        text="Data Fitxer",
        command=lambda: move_file_to(target_root / data_a_path(missing_files[state["idx"]][0])),
        width=14,
        bg="#55E1E3",
        fg="white",
        font=("Segoe UI", 10, "bold"),
        relief=tk.FLAT,
        cursor="hand2"
    )
    
    btn_from_file.pack(side=tk.LEFT, padx=4)

    add_tooltip(
        btn_from_file,
        lambda: f"Directori Fixer:\n{target_root / dest}"
            if (dest := data_a_path(missing_files[state["idx"]][0])) is not None
            else "No s'ha pogut deduir la data del nom del fitxer"    
    )

    tk.Button(btn_frame, text="Mou a...", command=move_file, width=14,
              bg="#4CAF50", fg="white", font=("Segoe UI", 10, "bold"),
              relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)
    tk.Button(btn_frame, text="Salta", command=skip_file, width=10,
              font=("Segoe UI", 10), relief=tk.FLAT,
              cursor="hand2").pack(side=tk.LEFT, padx=4)
    tk.Button(btn_frame, text="Surt", command=quit_review, width=10,
              bg="#c0392b", fg="white", font=("Segoe UI", 10),
              relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)

    root.after(150, show_current)
    root.mainloop()


def main():
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
    cache_dir = Path(args.cache_dir).resolve() if args.cache_dir else Path.cwd()

    if not source.is_dir():
        print(f"Error: l'origen '{source}' no es un directori valid.", file=sys.stderr)
        sys.exit(1)

    # -- Netejar cache origen (no cal escanar res) ----------------------------
    if args.netejar_cache_origen:
        cache_dir_early = Path(args.cache_dir).resolve() if args.cache_dir else Path.cwd()
        cf = cache_path_for(source, cache_dir_early)
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
    target_cache = load_cache(target_cache_file)
    last_scan_dst = target_cache.get("ultim_escaneig", "mai")
    print(f"Escaneant desti:  {target}", file=sys.stderr)
    print(f"  Ultim escaneig: {last_scan_dst}", file=sys.stderr)
    target_total = count_files(target)
    print(f"  {target_total} fitxers trobats. Calculant checksums...", file=sys.stderr)
    target_map, updated_target_cache = scan_directory(target, target_total, target_cache)
    target_checksums = set(target_map.values())
    save_cache(target_cache_file, updated_target_cache)
    print(f"  {len(target_checksums)} checksums unics. Cache desada: {target_cache_file.name}", file=sys.stderr)

    # Origen
    source_cache_file = cache_path_for(source, cache_dir)
    source_cache = load_cache(source_cache_file)
    last_scan_src = source_cache.get("ultim_escaneig", "mai")
    print(f"\nEscaneant origen: {source}", file=sys.stderr)
    print(f"  Ultim escaneig: {last_scan_src}", file=sys.stderr)
    source_total = count_files(source)
    print(f"  {source_total} fitxers trobats. Calculant checksums...", file=sys.stderr)
    source_map, updated_source_cache = scan_directory(source, source_total, source_cache)
    save_cache(source_cache_file, updated_source_cache)
    print(f"  Cache desada: {source_cache_file.name}", file=sys.stderr)

    # Fitxers mancants i fitxers presents (sync OK)
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

    # -- Script d'eliminacio --------------------------------------------------
    if args.script_eliminacio:
        script_path = Path(args.script_eliminacio)
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
        print(f"Script d'eliminacio desat a: {script_path}", file=sys.stderr)
        print(f"  {len(present)} fitxers llistats per eliminar.")

    # Fitxer de sortida
    if args.generar_sortida:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(args.sortida) if args.sortida else Path.cwd() / f"fitxers_mancants_{ts}.txt"
    
        with open(output_path, "w", encoding="utf-8") as out:
            out.write(f"Escaneig: {datetime.now().isoformat(timespec='seconds')}\n")
            out.write(f"Origen:   {source}\n")
            out.write(f"Desti:    {target}\n")
            out.write("=" * 60 + "\n\n")
            if not missing:
                out.write("Tots els fitxers de l'origen es troben al desti.\n")
                print("\nTots els fitxers de l'origen es troben al desti.")
            else:
                out.write(f"Fitxers NO trobats al desti ({len(missing)}):\n\n")
                for rel_path, checksum in missing:
                    if args.mostrar_checksum:
                        out.write(f"  {rel_path}  [{checksum}]\n")
                    else:
                        out.write(f"  {rel_path}\n")
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
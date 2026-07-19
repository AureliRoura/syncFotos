#!/usr/bin/env python3
from __future__ import annotations

import platform
import sys
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox

from ..core.review_ops import create_review_state, move_missing_file, restore_recent_moves
from ..core.sync_core import data_a_path


dragging = False
has_paused = False


def revisar_fitxers(missing_files, source_root, target_root):
    """
    Mostra les fotos mancants una a una i permet moure-les a un directori triat.
    Requereix: tkinter (stdlib). Pillow (pip install Pillow) per previsualitzar.
    """
    player = None
    vlc = None
    vlc_instance = None
    try:
        from PIL import Image, ImageTk
        HAS_PIL = True
    except ImportError:
        HAS_PIL = False
        print("[AVIS] Pillow no instal·lat; no es mostraran imatges.", file=sys.stderr)
        print("       Instal·leu-lo amb: pip install Pillow", file=sys.stderr)

    try:
        import vlc
        vlc_instance = vlc.Instance()
        player = vlc_instance.media_player_new()
    except Exception:
        print("[AVIS] VLC no instal·lat; no es podran reproduir vídeos.", file=sys.stderr)
        print("       Instal·leu-lo amb: pip install python-vlc", file=sys.stderr)
        vlc = None
        player = None

    state = create_review_state(target_root)
    closing = False
    after_jobs = []

    def center_window(window):
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        window.geometry(f"+{x}+{y}")

    def maximize_window(window):
        try:
            window.state("zoomed")
            if window.state() == "zoomed":
                return
        except tk.TclError:
            pass
        try:
            window.wm_attributes("-zoomed", True)
            return
        except tk.TclError:
            pass
        window.update_idletasks()
        sw = window.winfo_screenwidth()
        sh = window.winfo_screenheight()
        window.geometry(f"{sw}x{sh}+0+0")

    def on_press(event):
        global dragging, has_paused
        if player is None:
            return
        dragging = True
        if player.is_playing():
            player.pause()
            while player.get_state() != vlc.State.Paused:
                pass
            has_paused = True

    def on_release(event):
        global dragging, has_paused
        if player is None:
            return
        dragging = False
        player.set_position(video_pos.get() / 1000.0)
        if has_paused:
            player.play()
            has_paused = False

    def toggle_play():
        if player is None:
            return
        player.pause()

    def stop_video_playback():
        if player is None:
            return
        try:
            if player.is_playing():
                player.stop()
        except Exception:
            pass
        try:
            player.set_media(None)
        except Exception:
            pass

    def seek_video(value):
        if dragging and player is not None:
            player.set_position(float(value) / 1000.0)

    def update_video_position():
        if closing:
            return
        if player is not None:
            if player.is_playing() and not dragging:
                pos = player.get_position()
                if pos >= 0:
                    video_pos.set(int(pos * 1000))

            after_jobs.append(root.after(250, update_video_position))

    root = tk.Tk()
    root.title("Revisar fotos mancants")
    root.geometry("960x740")
    root.configure(bg="#1e1e1e")
    root.after(0, lambda: maximize_window(root))

    info_var = tk.StringVar()
    tk.Label(root, textvariable=info_var, bg="#1e1e1e", fg="#dddddd",
             font=("Segoe UI", 10), anchor="w", wraplength=940).pack(
        fill=tk.X, padx=10, pady=(10, 4))

    _img_ref = [None]

    viewer = tk.Frame(root)
    viewer.pack(expand=True, fill=tk.BOTH, padx=10)
    canvas = tk.Canvas(viewer, bg="#111111", highlightthickness=0)
    canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

    video_frame = tk.Frame(viewer, bg="#111111")
    video_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
    video_frame.lower()
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

    btn_frame = tk.Frame(root, bg="#1e1e1e")
    btn_frame.pack(fill=tk.X, padx=10, pady=8)

    stats_var = tk.StringVar()
    tk.Label(btn_frame, textvariable=stats_var, bg="#1e1e1e", fg="#aaaaaa",
             font=("Segoe UI", 9)).pack(side=tk.RIGHT, padx=12)
    if vlc is not None and player is not None:
        update_video_position()

    def close_review():
        nonlocal closing
        if closing:
            return
        closing = True
        try:
            stop_video_playback()
            if player is not None:
                try:
                    player.release()
                except Exception:
                    pass
            if vlc_instance is not None:
                try:
                    vlc_instance.release()
                except Exception:
                    pass
        finally:
            try:
                for job in after_jobs:
                    try:
                        root.after_cancel(job)
                    except Exception:
                        pass
            finally:
                root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_review)

    def add_tooltip(widget, text_func):
        tip = None

        def enter(event):
            nonlocal tip
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
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
            tip.update_idletasks()
            tip_w = tip.winfo_width()
            tip_h = tip.winfo_height()
            screen_w = widget.winfo_screenwidth()
            screen_h = widget.winfo_screenheight()
            x = event.x_root + 12
            y = event.y_root + 12
            if x + tip_w > screen_w:
                x = event.x_root - tip_w - 12
            MARGE = 40
            if y + tip_h > screen_h - MARGE:
                y = event.y_root - tip_h - 12
            x = max(0, x)
            y = max(0, y)
            tip.wm_geometry(f"+{x}+{y}")

        def leave(event):
            nonlocal tip
            if tip:
                tip.destroy()
                tip = None

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def update_stats():
        stats_var.set(f"Mogudes: {state.mogudes}  |  Saltades: {state.saltades}")

    def load_video(path):
        if vlc is None:
            video_frame.lift()
            for widget in video_frame.winfo_children():
                widget.destroy()
            tk.Label(
                video_frame,
                text=(
                    "No es pot reproduir el vídeo.\n\n"
                    "No s'ha trobat VLC Media Player o la llibreria python-vlc."
                ),
                justify=tk.CENTER,
                font=("Segoe UI", 11),
                fg="#888888"
            ).pack(expand=True)
            video_controls.pack_forget()
            print("[AVIS] VLC no disponible; no es pot reproduir el video.", file=sys.stderr)
            return
        if not video_controls.winfo_ismapped():
            video_controls.pack(before=btn_frame, fill=tk.X, padx=10, pady=(0, 5))
        stop_video_playback()
        video_frame.lift()
        video_frame.update()
        wid = video_frame.winfo_id()
        media = vlc_instance.media_new(str(path))
        player.set_media(media)
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
        if vlc is not None and player is not None:
            stop_video_playback()
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
        if closing:
            return
        total = len(missing_files)
        if state.idx >= total:
            messagebox.showinfo(
                "Revisio completada",
                f"S'han revisat tots els fitxers.\n\nMogudes: {state.mogudes}\nSaltades: {state.saltades}"
            )
            close_review()
            return
        if data_a_path(missing_files[state.idx][0], target_root) is None:
            btn_from_file.config(state=tk.DISABLED)
        else:
            btn_from_file.config(state=tk.NORMAL)
        rel_path, _ = missing_files[state.idx]
        full_path = source_root / rel_path
        root.title(f"Revisar fotos mancants  ({state.idx + 1}/{total})")
        info_var.set(f"{state.idx + 1} / {total}   \u2192   {rel_path}")
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
            initialdir=str(state.last_dir),
            parent=root,
        )
        if chosen:
            move_file_to(Path(chosen))

    def move_file_to(dest_dir: Path):
        rel_path, _ = missing_files[state.idx]
        try:
            move_missing_file(source_root, rel_path, dest_dir, state)
            show_current()
        except OSError as e:
            messagebox.showerror("Error en moure", str(e))

    def skip_file():
        state.saltades += 1
        state.idx += 1
        show_current()

    def quit_review():
        if messagebox.askyesno(
            "Sortir",
            f"Sortir de la revisio?\n\nMogudes: {state.mogudes}\nSaltades: {state.saltades}"
        ):
            close_review()

    btn_last = tk.Button(
        btn_frame,
        text="Mou últim",
        command=lambda: move_file_to(state.last_dir),
        width=14,
        bg="#2E86C1",
        fg="white",
        font=("Segoe UI", 10, "bold"),
        relief=tk.FLAT,
        cursor="hand2"
    )
    btn_last.pack(side=tk.LEFT, padx=4)

    add_tooltip(btn_last, lambda: f"Últim directori:\n{state.last_dir}")

    btn_from_file = tk.Button(
        btn_frame,
        text="Data Fitxer",
        command=lambda: move_file_to(target_root / data_a_path(missing_files[state.idx][0], target_root)),
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
            if (dest := data_a_path(missing_files[state.idx][0], target_root)) is not None
            else "No s'ha pogut deduir la data del nom del fitxer"
    )

    tk.Button(btn_frame, text="Mou a...", command=move_file, width=14,
              bg="#4CAF50", fg="white", font=("Segoe UI", 10, "bold"),
              relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)
    tk.Button(btn_frame, text="Salta", command=skip_file, width=10,
              font=("Segoe UI", 10), relief=tk.FLAT,
              cursor="hand2").pack(side=tk.LEFT, padx=4)

    def undo_files():
        hist = state.historial
        if not hist:
            messagebox.showinfo("Desfer", "No hi ha cap moviment per desfer.")
            return

        recent = hist[-10:][::-1]

        dlg = tk.Toplevel(root)
        dlg.title("Desfer moviments")
        dlg.configure(bg="#1e1e1e")
        dlg.resizable(True, True)
        dlg.geometry("700x500")

        def maximize_dialog():
            try:
                dlg.state("zoomed")
                if dlg.state() == "zoomed":
                    return
            except tk.TclError:
                pass
            try:
                dlg.wm_attributes("-zoomed", True)
                return
            except tk.TclError:
                pass
            # Fallback: ocupar tota la pantalla quan el gestor de finestres
            # no suporta estats de maximitzacio de Tk.
            dlg.update_idletasks()
            sw = dlg.winfo_screenwidth()
            sh = dlg.winfo_screenheight()
            dlg.geometry(f"{sw}x{sh}+0+0")

        dlg.after(0, maximize_dialog)
        dlg.grab_set()

        tk.Label(
            dlg,
            text="Selecciona els fitxers que vols tornar a l'origen:",
            bg="#1e1e1e", fg="#dddddd",
            font=("Segoe UI", 10, "bold"),
        ).pack(padx=14, pady=(12, 6), anchor="w")

        canvas_frame = tk.Frame(dlg, bg="#1e1e1e")
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)

        canvas = tk.Canvas(canvas_frame, bg="#1e1e1e", highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#1e1e1e")

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        vars_ = []
        dlg._img_refs = []
        for orig, dest in recent:
            var = tk.BooleanVar(value=False)
            vars_.append((var, orig, dest))
            frame_row = tk.Frame(scrollable_frame, bg="#1e1e1e")
            frame_row.pack(fill=tk.X, pady=6, anchor="w")
            tk.Checkbutton(
                frame_row, variable=var,
                bg="#1e1e1e", fg="#dddddd",
                selectcolor="#333333",
                activebackground="#1e1e1e", activeforeground="#ffffff",
                font=("Segoe UI", 9),
            ).pack(side=tk.LEFT, padx=(0, 12))
            ext = dest.suffix.lower()
            if HAS_PIL and ext in {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}:
                try:
                    img = Image.open(dest)
                    img.thumbnail((70, 70), Image.LANCZOS)
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    photo = ImageTk.PhotoImage(img)
                    dlg._img_refs.append(photo)
                    img_label = tk.Label(frame_row, image=photo, bg="#1e1e1e", relief=tk.SUNKEN)
                    img_label.pack(side=tk.LEFT, padx=(0, 12))
                except Exception as e:
                    print(f"[DEBUG] Error carregant imatge {dest}: {e}", file=sys.stderr)

            tk.Label(
                frame_row,
                text=f"{dest.name}  →  {orig.parent}",
                bg="#1e1e1e", fg="#aaaaaa",
                font=("Segoe UI", 9),
                anchor="w",
                wraplength=400,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        def confirmar():
            errors = []
            selected_moves = [(orig, dest) for var, orig, dest in vars_ if var.get()]
            try:
                restored = restore_recent_moves(selected_moves, state)
            except OSError as e:
                errors.append(str(e))
                restored = []

            update_stats()
            dlg.destroy()
            if errors:
                messagebox.showerror("Errors en restaurar", "\n".join(errors))
            elif restored:
                restored_entries = []
                restored_rel_paths = {
                    str(orig.relative_to(source_root))
                    for orig, _ in restored
                }
                remaining_entries = []
                for entry in missing_files:
                    rel_path = entry[0]
                    rel_key = str(Path(rel_path))
                    if rel_key in restored_rel_paths:
                        restored_entries.append(entry)
                    else:
                        remaining_entries.append(entry)

                missing_files[:] = restored_entries + remaining_entries
                state.idx = 0
                show_current()
                messagebox.showinfo("Desfer completat", f"S'han restaurat {len(restored)} fitxer(s).")

        btn_row = tk.Frame(dlg, bg="#1e1e1e")
        btn_row.pack(pady=(10, 12), padx=14, anchor="e")
        tk.Button(btn_row, text="Restaura seleccionats", command=confirmar,
                  bg="#e67e22", fg="white",
                  font=("Segoe UI", 10, "bold"),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="Cancel·la", command=dlg.destroy,
                  font=("Segoe UI", 10), relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)

    tk.Button(btn_frame, text="Desfer", command=undo_files, width=10,
              bg="#e67e22", fg="white", font=("Segoe UI", 10),
              relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)
    tk.Button(btn_frame, text="Surt", command=quit_review, width=10,
              bg="#c0392b", fg="white", font=("Segoe UI", 10),
              relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)

    root.after(150, show_current)
    root.mainloop()

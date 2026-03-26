import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD
from CTkMessagebox import CTkMessagebox
from logic import elabora_documento, get_documents_path, COMPRESS_PRESETS
from PIL import Image
import os, fitz, sys, re, platform, io, subprocess
from pathlib import Path


# ============================================================
#  Helpers cross-platform
# ============================================================

def _get_tkdnd_subdir() -> "str | None":
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        return "win-x64" if sys.maxsize > 2**32 else "win-x86"
    elif system == "Darwin":
        return "osx-arm64" if machine == "arm64" else "osx-x86_64"
    elif system == "Linux":
        if "aarch64" in machine or "arm64" in machine:
            return "linux-aarch64"
        return "linux-x86_64" if sys.maxsize > 2**32 else "linux-x86"
    return None


def _parse_drop_paths(data: str) -> list:
    """Parsa la stringa di drop di tkinterdnd2 in modo cross-platform."""
    paths = []
    current = data.strip()
    while current:
        if current.startswith("{"):
            end = current.find("}")
            if end == -1:
                break
            paths.append(current[1:end])
            current = current[end + 1:].strip()
        else:
            space = current.find(" ")
            if space == -1:
                paths.append(current)
                break
            paths.append(current[:space])
            current = current[space:].strip()
    return paths


def _open_in_file_manager(path: Path) -> None:
    """Apre la cartella nel file manager nativo (Windows / macOS / Linux)."""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(path))
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


# ============================================================
#  Dialogo esclusione pagine  (invariato rispetto all'originale)
# ============================================================

class ExclusionDialog(ctk.CTkToplevel):
    def __init__(self, master, current_exclusions: str, max_pagine: int):
        super().__init__(master)
        self.title("Escludi Pagine")
        self.geometry("400x250")
        self.max_pagine = max_pagine
        self.result = current_exclusions

        ctk.CTkLabel(
            self,
            text="Inserisci pagine o intervalli da ESCLUDERE\n(es: 1, 3-5, 10)",
            font=("Roboto", 13),
        ).pack(pady=20)

        self.entry = ctk.CTkEntry(self, width=300)
        self.entry.insert(0, current_exclusions)
        self.entry.pack(pady=10)

        ctk.CTkButton(self, text="Conferma", command=self.confirm).pack(pady=20)
        self.transient(master)
        self.grab_set()

    def confirm(self):
        self.result = self.entry.get()
        self.destroy()


# ============================================================
#  Anteprima merge  ★ NUOVO
# ============================================================

class PreviewDialog(ctk.CTkToplevel):
    """
    Mostra una miniatura del primo affiancamento che verrà prodotto
    per un determinato PDFItem, rispettando la modalità Orientale/Occidentale.
    """
    _SCALE = 0.22  # fattore di riduzione per il rendering

    def __init__(self, master, item_data: dict, manga_mode: bool):
        super().__init__(master)
        self.title("Anteprima merge")
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()
        self._render(item_data, manga_mode)

    # ------------------------------------------------------------------
    def _render(self, data: dict, manga_mode: bool) -> None:
        try:
            doc = fitz.open(data["path"])
            pagine_valide = [
                p for p in range(data["start"], data["end"])
                if p not in data["exclude"] and p < len(doc)
            ]

            if not pagine_valide:
                ctk.CTkLabel(
                    self,
                    text="Nessuna pagina nel range selezionato.",
                    font=("Roboto", 13),
                ).pack(padx=20, pady=30)
                self.geometry("380x100")
                doc.close()
                return

            mat = fitz.Matrix(self._SCALE, self._SCALE)

            def to_ctk(idx: int) -> tuple:
                pix = doc[idx].get_pixmap(matrix=mat)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                return (
                    ctk.CTkImage(light_image=img, dark_image=img,
                                 size=(img.width, img.height)),
                    img.width,
                    img.height,
                )

            if len(pagine_valide) >= 2:
                # Orientale: la pagina di DESTRA va mostrata per prima visivamente
                if manga_mode:
                    left_idx, right_idx = pagine_valide[1], pagine_valide[0]
                    left_num, right_num = pagine_valide[1] + 1, pagine_valide[0] + 1
                else:
                    left_idx, right_idx = pagine_valide[0], pagine_valide[1]
                    left_num, right_num = pagine_valide[0] + 1, pagine_valide[1] + 1

                img_l, wl, hl = to_ctk(left_idx)
                img_r, wr, hr = to_ctk(right_idx)

                row = ctk.CTkFrame(self, fg_color="transparent")
                row.pack(padx=10, pady=(10, 4))
                ctk.CTkLabel(row, image=img_l, text="").pack(side="left", padx=2)

                # separatore verticale
                ctk.CTkFrame(row, width=2, fg_color="#3b8ed0").pack(
                    side="left", fill="y", pady=4)

                ctk.CTkLabel(row, image=img_r, text="").pack(side="left", padx=2)

                mode_str = "Orientale  ←  (destra → sinistra)" if manga_mode \
                           else "Occidentale  →  (sinistra → destra)"
                ctk.CTkLabel(
                    self,
                    text=f"Modalità: {mode_str}\n"
                         f"Pag. {left_num}  |  Pag. {right_num}",
                    font=("Roboto", 11),
                    text_color="#95A5A6",
                ).pack(pady=(0, 10))

                total_w = wl + wr + 60
                total_h = max(hl, hr) + 90
                self.geometry(f"{total_w}x{total_h}")

            else:
                img, w, h = to_ctk(pagine_valide[0])
                ctk.CTkLabel(self, image=img, text="").pack(padx=10, pady=10)
                ctk.CTkLabel(
                    self,
                    text=f"Solo 1 pagina nel range — verrà inserita singola (pag. {pagine_valide[0]+1})",
                    font=("Roboto", 11),
                    text_color="#F39C12",
                ).pack(pady=(0, 10))
                self.geometry(f"{w + 40}x{h + 80}")

            doc.close()

        except Exception as exc:
            ctk.CTkLabel(
                self,
                text=f"Impossibile generare l'anteprima:\n{exc}",
                font=("Roboto", 12),
                text_color="#E74C3C",
            ).pack(padx=20, pady=30)
            self.geometry("420x130")


# ============================================================
#  Dialogo log errori  ★ NUOVO
# ============================================================

class ErrorLogDialog(ctk.CTkToplevel):
    """
    Mostra i file che hanno generato errori durante il merge
    con il relativo messaggio di eccezione.
    """

    def __init__(self, master, errors: list):
        super().__init__(master)
        self.title("Log Errori")
        self.geometry("520x360")
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(
            self,
            text=f"⚠️   {len(errors)} file non elaborati",
            font=("Roboto", 14, "bold"),
            text_color="#E74C3C",
        ).pack(pady=(14, 6))

        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=12, pady=4)

        for fname, msg in errors:
            card = ctk.CTkFrame(scroll, fg_color="#2C3E50", corner_radius=6)
            card.pack(fill="x", pady=3, padx=4)
            ctk.CTkLabel(
                card, text=fname,
                font=("Roboto", 12, "bold"), text_color="#E74C3C",
            ).pack(anchor="w", padx=10, pady=(6, 0))
            ctk.CTkLabel(
                card, text=msg,
                font=("Roboto", 11), text_color="#95A5A6",
                wraplength=460, justify="left",
            ).pack(anchor="w", padx=10, pady=(0, 6))

        ctk.CTkButton(self, text="Chiudi", command=self.destroy).pack(pady=10)


# ============================================================
#  Singolo elemento PDF nella lista
# ============================================================

class PDFItem(ctk.CTkFrame):
    """
    Widget che rappresenta un PDF nella lista.
    Espone get_data() per la logica e get_state()/restore_state()
    per l'undo/redo.
    """

    def __init__(self, master, file_path: str, app: "PDFPageMergerGUI"):
        super().__init__(master)
        self.file_path = file_path
        self.app = app
        self.exclusions = ""
        self._drag_y_anchor: int = 0  # y_root al momento del press

        doc = fitz.open(file_path)
        self.max_pagine = len(doc)
        doc.close()

        is_single = self.max_pagine <= 1
        slider_to = 1.1 if is_single else self.max_pagine
        steps = 1 if is_single else self.max_pagine - 1

        # ----------------------------------------------------------------
        # Header
        # ----------------------------------------------------------------
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=10, pady=(6, 0))

        # — Drag handle (⠿)
        drag_lbl = ctk.CTkLabel(
            self.header, text="⠿",
            font=("Roboto", 18), text_color="#5D6D7E", cursor="fleur",
        )
        drag_lbl.pack(side="left", padx=(0, 6))
        drag_lbl.bind("<ButtonPress-1>",   self._drag_start)
        drag_lbl.bind("<B1-Motion>",       self._drag_motion)
        drag_lbl.bind("<ButtonRelease-1>", self._drag_end)

        # — Nome file
        ctk.CTkLabel(
            self.header,
            text=os.path.basename(file_path),
            font=("Roboto", 12, "bold"),
            text_color="#2ecc71",
        ).pack(side="left")

        # — Info pagine
        ctk.CTkLabel(
            self.header,
            text=f"  •  {self.max_pagine} pag.",
            font=("Roboto", 11),
            text_color="#95A5A6",
        ).pack(side="left")

        # — Pulsanti a destra (impilati da destra verso sinistra)
        ctk.CTkButton(
            self.header, text="✕", width=26, height=22,
            fg_color="#C0392B", hover_color="#A93226",
            command=lambda: app.rimuovi_pdf(self),
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            self.header, text="▼", width=26, height=22,
            fg_color="#34495E", hover_color="#2C3E50",
            command=lambda: app.muovi_giu(self),
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            self.header, text="▲", width=26, height=22,
            fg_color="#34495E", hover_color="#2C3E50",
            command=lambda: app.muovi_su(self),
        ).pack(side="right", padx=2)

        # — Esclusioni (...)
        self.btn_dots = ctk.CTkButton(
            self.header, text="...", width=32, height=22,
            fg_color="#5D6D7E", hover_color="#4A5568",
            command=self.open_exclusion_dialog,
        )
        self.btn_dots.pack(side="right", padx=2)

        # — Anteprima (👁)  ★ NUOVO
        ctk.CTkButton(
            self.header, text="👁", width=32, height=22,
            fg_color="#1A5276", hover_color="#154360",
            command=lambda: app.mostra_anteprima(self),
        ).pack(side="right", padx=2)

        # ----------------------------------------------------------------
        # Copertina singola  ★ NUOVO
        # ----------------------------------------------------------------
        self.cover_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self,
            text="Copertina singola  (pag. 1 sempre sola, non affiancata)",
            variable=self.cover_var,
            font=("Roboto", 11),
        ).pack(anchor="w", padx=22, pady=(6, 0))

        # ----------------------------------------------------------------
        # Slider  Inizio
        # ----------------------------------------------------------------
        self.label_s = ctk.CTkLabel(self, text="Inizio: 1", font=("Roboto", 13, "bold"))
        self.label_s.pack(padx=20, anchor="w", pady=(4, 0))
        self.slider_s = ctk.CTkSlider(
            self, from_=1, to=slider_to, number_of_steps=steps,
            height=18, command=self.update_labels,
        )
        self.slider_s.set(1)
        self.slider_s.pack(fill="x", padx=20)

        # ----------------------------------------------------------------
        # Slider  Fine
        # ----------------------------------------------------------------
        self.label_e = ctk.CTkLabel(
            self, text=f"Fine: {self.max_pagine}", font=("Roboto", 13, "bold"))
        self.label_e.pack(padx=20, anchor="w", pady=(4, 0))
        self.slider_e = ctk.CTkSlider(
            self, from_=1, to=slider_to, number_of_steps=steps,
            height=18, command=self.update_labels,
        )
        self.slider_e.set(self.max_pagine)
        self.slider_e.pack(fill="x", padx=20, pady=(0, 10))

        if is_single:
            self.slider_s.configure(state="disabled")
            self.slider_e.configure(state="disabled")

    # ----------------------------------------------------------------
    # Drag & drop interno  ★ NUOVO
    # ----------------------------------------------------------------

    def _drag_start(self, event) -> None:
        self._drag_y_anchor = event.y_root
        self.app._drag_item = self

    def _drag_motion(self, event) -> None:
        if self.app._drag_item is not self:
            return
        dy = event.y_root - self._drag_y_anchor
        # Soglia: metà dell'altezza corrente del widget (adattiva al contenuto)
        threshold = max(self.winfo_height() * 0.45, 30)
        idx = self.app.items.index(self)

        if dy < -threshold and idx > 0:
            self.app._drag_snapshot()
            self.app._swap_items(idx, idx - 1)
            self._drag_y_anchor = event.y_root
        elif dy > threshold and idx < len(self.app.items) - 1:
            self.app._drag_snapshot()
            self.app._swap_items(idx, idx + 1)
            self._drag_y_anchor = event.y_root

    def _drag_end(self, event) -> None:
        self.app._drag_item = None
        self.app._drag_snapped = False

    # ----------------------------------------------------------------
    # Esclusioni
    # ----------------------------------------------------------------

    def open_exclusion_dialog(self) -> None:
        dialog = ExclusionDialog(self.winfo_toplevel(), self.exclusions, self.max_pagine)
        self.master.wait_window(dialog)
        self.exclusions = dialog.result
        self.btn_dots.configure(
            fg_color="#F39C12" if self.exclusions.strip() else "#5D6D7E"
        )

    def parse_exclusions(self) -> set:
        excluded: set = set()
        for part in re.split(r"[,\s]+", self.exclusions):
            if "-" in part:
                try:
                    s, e = map(int, part.split("-"))
                    excluded.update(range(s - 1, e))
                except ValueError:
                    pass
            elif part.isdigit():
                excluded.add(int(part) - 1)
        return excluded

    # ----------------------------------------------------------------
    # Aggiornamento label slider
    # ----------------------------------------------------------------

    def update_labels(self, _=None) -> None:
        s, e = int(self.slider_s.get()), int(self.slider_e.get())
        if s > e:
            self.slider_s.set(e)
            s = e
        self.label_s.configure(text=f"Inizio: {s}")
        self.label_e.configure(text=f"Fine: {e}")

    # ----------------------------------------------------------------
    # Dati per la logica e l'undo/redo
    # ----------------------------------------------------------------

    def get_data(self) -> dict:
        return {
            "path":        self.file_path,
            "start":       int(self.slider_s.get()) - 1,
            "end":         int(self.slider_e.get()),
            "exclude":     self.parse_exclusions(),
            "cover_alone": self.cover_var.get(),
        }

    def get_state(self) -> dict:
        """Snapshot completo per undo/redo."""
        return {
            "path":        self.file_path,
            "slider_s":    self.slider_s.get(),
            "slider_e":    self.slider_e.get(),
            "exclusions":  self.exclusions,
            "cover_alone": self.cover_var.get(),
        }

    def restore_state(self, state: dict) -> None:
        """Ripristina lo stato da uno snapshot."""
        self.exclusions = state["exclusions"]
        self.slider_s.set(state["slider_s"])
        self.slider_e.set(state["slider_e"])
        self.cover_var.set(state["cover_alone"])
        self.update_labels()
        self.btn_dots.configure(
            fg_color="#F39C12" if self.exclusions.strip() else "#5D6D7E"
        )


# ============================================================
#  Finestra principale
# ============================================================

class PDFPageMergerGUI(ctk.CTk, TkinterDnD.DnDWrapper):
    _MAX_UNDO = 25

    def __init__(self):
        super().__init__()
        self._inizializza_tkdnd()

        self.title("PDF Page Merger")
        self.geometry("740x720")
        self.minsize(560, 500)

        # Stato interno
        self.items: list = []
        self._undo_stack: list = []
        self._redo_stack: list = []
        self._drag_item = None
        self._drag_snapped = False          # snapshot già salvato per il drag corrente
        self._is_restoring = False          # guard per evitare snapshot ricorsivi

        # Cartella output  ★ NUOVO
        default_out = get_documents_path() / "pdf-page-merger"
        self.output_dir_var = ctk.StringVar(value=str(default_out))

        # Tema corrente
        self._theme_mode = ctk.get_appearance_mode().lower()  # "dark" o "light"

        self._build_ui()
        self._bind_mouse_wheel(self)

        # Shortcut tastiera  ★ NUOVO
        self.bind("<Control-z>",       lambda _e: self._undo())
        self.bind("<Control-y>",       lambda _e: self._redo())
        self.bind("<Control-Z>",       lambda _e: self._redo())   # Ctrl+Shift+Z

    # ============================================================
    #  Inizializzazione tkdnd  (invariato)
    # ============================================================

    def _inizializza_tkdnd(self):
        try:
            import tkinterdnd2
            subdir = _get_tkdnd_subdir()
            if subdir is None:
                return
            path = os.path.join(os.path.dirname(tkinterdnd2.__file__), "tkdnd", subdir)
            self.tk.call("lappend", "auto_path", path)
            self.tk.call("package", "require", "tkdnd")
        except Exception:
            pass

    # ============================================================
    #  Mouse wheel  (invariato)
    # ============================================================

    def _bind_mouse_wheel(self, widget):
        try:
            widget.bind("<MouseWheel>", self._on_mouse_wheel)
            widget.bind("<Button-4>",   self._on_mouse_wheel)
            widget.bind("<Button-5>",   self._on_mouse_wheel)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_mouse_wheel(child)

    def _on_mouse_wheel(self, event):
        if not self.items:
            return
        direction = (-1 if event.delta > 0 else 1) if event.delta != 0 \
                    else (-1 if event.num == 4 else 1)
        try:
            self.scroll_frame._parent_canvas.yview_scroll(direction, "units")
        except Exception:
            pass

    # ============================================================
    #  Costruzione interfaccia
    # ============================================================

    def _build_ui(self):
        # ---- Barra superiore ----------------------------------------
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(12, 0))

        ctk.CTkLabel(
            top, text="📚 PDF Page Merger", font=("Roboto", 22, "bold"),
        ).pack(side="left")

        # Tema  ★ NUOVO
        icon = "☀️" if self._theme_mode == "dark" else "🌙"
        self.btn_theme = ctk.CTkButton(
            top, text=icon, width=38, height=28,
            fg_color="transparent", hover_color="#2C3E50",
            command=self._toggle_theme,
        )
        self.btn_theme.pack(side="right", padx=(4, 0))

        # Redo  ★ NUOVO
        self.btn_redo = ctk.CTkButton(
            top, text="↪  Redo", width=80, height=28,
            fg_color="#1A5276", hover_color="#154360",
            state="disabled", command=self._redo,
        )
        self.btn_redo.pack(side="right", padx=2)

        # Undo  ★ NUOVO
        self.btn_undo = ctk.CTkButton(
            top, text="↩  Undo", width=80, height=28,
            fg_color="#1A5276", hover_color="#154360",
            state="disabled", command=self._undo,
        )
        self.btn_undo.pack(side="right", padx=2)

        # ---- Modalità lettura ----------------------------------------
        self.style_var = ctk.StringVar(value="Orientale")
        ctk.CTkSegmentedButton(
            self, values=["Orientale", "Occidentale"],
            variable=self.style_var,
        ).pack(pady=8)

        # ---- Riga opzioni (compressione)  ★ NUOVO ------------------
        opt = ctk.CTkFrame(self, fg_color="transparent")
        opt.pack(fill="x", padx=18, pady=(0, 4))

        ctk.CTkLabel(opt, text="Compressione output:",
                     font=("Roboto", 12)).pack(side="left")
        self.compress_var = ctk.StringVar(value="Media")
        ctk.CTkComboBox(
            opt,
            values=list(COMPRESS_PRESETS.keys()),
            variable=self.compress_var,
            width=120,
        ).pack(side="left", padx=(6, 0))

        # ---- Cartella output  ★ NUOVO --------------------------------
        out_row = ctk.CTkFrame(self, fg_color="transparent")
        out_row.pack(fill="x", padx=18, pady=(0, 6))

        ctk.CTkLabel(out_row, text="📂  Output:", font=("Roboto", 12)).pack(side="left")
        ctk.CTkLabel(
            out_row,
            textvariable=self.output_dir_var,
            font=("Roboto", 11), text_color="#95A5A6",
            anchor="w",
        ).pack(side="left", padx=6, fill="x", expand=True)
        ctk.CTkButton(
            out_row, text="Cambia", width=72, height=26,
            fg_color="#1b5e20", hover_color="#145A32",
            command=self._select_output_dir,
        ).pack(side="right")

        # ---- Drop zone -----------------------------------------------
        self.drop_frame = ctk.CTkFrame(
            self, height=68, border_width=2, border_color="#3b8ed0")
        self.drop_frame.pack(pady=6, padx=18, fill="x")
        self.drop_frame.pack_propagate(False)
        ctk.CTkLabel(
            self.drop_frame,
            text="Trascina qui i PDF  •  Puoi trascinare più file contemporaneamente",
        ).pack(expand=True)
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind("<<Drop>>", self.gestisci_drop)

        ctk.CTkButton(
            self, text="📁  Seleziona File", command=self.seleziona_file,
            fg_color="#1b5e20", hover_color="#145A32", height=32,
        ).pack(pady=4)

        # ---- Lista documenti (scrollable) ----------------------------
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Lista Documenti")
        # verrà mostrato al primo file aggiunto

        # ---- Contenitore progresso  ★ NUOVO (nascosto di default) ---
        self.progress_container = ctk.CTkFrame(self, fg_color="transparent")

        self.lbl_file_corrente = ctk.CTkLabel(
            self.progress_container, text="",
            font=("Roboto", 11), text_color="#95A5A6",
        )
        self.lbl_file_corrente.pack(pady=(6, 0))

        self.progress_file = ctk.CTkProgressBar(self.progress_container)
        self.progress_file.set(0)
        self.progress_file.pack(fill="x", padx=50, pady=2)

        self.lbl_totale = ctk.CTkLabel(
            self.progress_container, text="",
            font=("Roboto", 11), text_color="#95A5A6",
        )
        self.lbl_totale.pack()

        self.progress_bar = ctk.CTkProgressBar(self.progress_container)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=50, pady=(2, 8))

        # ---- Pulsante MERGE PDF (sempre in fondo) --------------------
        self.btn_avvia = ctk.CTkButton(
            self, text="MERGE PDF", command=self.esegui,
            state="disabled", font=("Roboto", 14, "bold"), height=42,
        )
        self.btn_avvia.pack(pady=12, side="bottom")

    # ============================================================
    #  Azioni UI
    # ============================================================

    def seleziona_file(self):
        paths = ctk.filedialog.askopenfilenames(filetypes=[("PDF Files", "*.pdf")])
        for p in paths:
            self.aggiungi_pdf(p)

    def gestisci_drop(self, event):
        for p in _parse_drop_paths(event.data):
            if p.lower().endswith(".pdf"):
                self.aggiungi_pdf(p)

    def aggiungi_pdf(self, path: str):
        # ★ Rilevamento duplicati
        if any(item.file_path == path for item in self.items):
            CTkMessagebox(
                title="File già presente",
                message=f"Questo PDF è già in lista:\n{os.path.basename(path)}",
                icon="warning",
            )
            return

        self._snapshot()  # ★ undo

        if not self.items:
            self.scroll_frame.pack(
                pady=5, padx=18, fill="both", expand=True,
                before=self.btn_avvia,
            )

        item = PDFItem(self.scroll_frame, path, self)
        item.pack(fill="x", pady=5, padx=5)
        self.items.append(item)
        self._bind_mouse_wheel(item)
        self.btn_avvia.configure(state="normal")

    def rimuovi_pdf(self, item):
        self._snapshot()  # ★ undo
        item.destroy()
        self.items.remove(item)
        if not self.items:
            self.scroll_frame.pack_forget()
            self.btn_avvia.configure(state="disabled")

    def muovi_su(self, item):
        idx = self.items.index(item)
        if idx > 0:
            self._snapshot()  # ★ undo
            self.items[idx], self.items[idx - 1] = self.items[idx - 1], self.items[idx]
            self.refresh_list()

    def muovi_giu(self, item):
        idx = self.items.index(item)
        if idx < len(self.items) - 1:
            self._snapshot()  # ★ undo
            self.items[idx], self.items[idx + 1] = self.items[idx + 1], self.items[idx]
            self.refresh_list()

    def refresh_list(self):
        for item in self.items:
            item.pack_forget()
            item.pack(fill="x", pady=5, padx=5)

    # ============================================================
    #  Drag & drop interno  ★ NUOVO
    # ============================================================

    def _drag_snapshot(self):
        """Salva snapshot solo al primo swap del drag corrente."""
        if not self._drag_snapped:
            self._snapshot()
            self._drag_snapped = True

    def _swap_items(self, a: int, b: int):
        self.items[a], self.items[b] = self.items[b], self.items[a]
        self.refresh_list()

    # ============================================================
    #  Undo / Redo  ★ NUOVO
    # ============================================================

    def _snapshot(self):
        """Salva lo stato corrente nello stack undo."""
        if self._is_restoring:
            return
        state = [item.get_state() for item in self.items]
        self._undo_stack.append(state)
        if len(self._undo_stack) > self._MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_ud_buttons()

    def _undo(self):
        if not self._undo_stack:
            return
        self._redo_stack.append([item.get_state() for item in self.items])
        self._restore_state(self._undo_stack.pop())
        self._update_ud_buttons()

    def _redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append([item.get_state() for item in self.items])
        self._restore_state(self._redo_stack.pop())
        self._update_ud_buttons()

    def _restore_state(self, state: list):
        self._is_restoring = True
        try:
            for item in self.items[:]:
                item.destroy()
            self.items.clear()

            for s in state:
                item = PDFItem(self.scroll_frame, s["path"], self)
                item.pack(fill="x", pady=5, padx=5)
                item.restore_state(s)
                self.items.append(item)
                self._bind_mouse_wheel(item)

            if self.items:
                # Assicura che scroll_frame sia visibile
                try:
                    self.scroll_frame.pack_info()
                except Exception:
                    self.scroll_frame.pack(
                        pady=5, padx=18, fill="both", expand=True,
                        before=self.btn_avvia,
                    )
                self.btn_avvia.configure(state="normal")
            else:
                self.scroll_frame.pack_forget()
                self.btn_avvia.configure(state="disabled")
        finally:
            self._is_restoring = False

    def _update_ud_buttons(self):
        self.btn_undo.configure(state="normal" if self._undo_stack else "disabled")
        self.btn_redo.configure(state="normal" if self._redo_stack else "disabled")

    # ============================================================
    #  Anteprima  ★ NUOVO
    # ============================================================

    def mostra_anteprima(self, item):
        PreviewDialog(self, item.get_data(), self.style_var.get() == "Orientale")

    # ============================================================
    #  Tema  ★ NUOVO
    # ============================================================

    def _toggle_theme(self):
        self._theme_mode = "light" if self._theme_mode == "dark" else "dark"
        ctk.set_appearance_mode(self._theme_mode)
        self.btn_theme.configure(
            text="☀️" if self._theme_mode == "dark" else "🌙"
        )

    # ============================================================
    #  Cartella output  ★ NUOVO
    # ============================================================

    def _select_output_dir(self):
        chosen = ctk.filedialog.askdirectory(
            title="Scegli la cartella di output",
            initialdir=self.output_dir_var.get(),
        )
        if chosen:
            self.output_dir_var.set(chosen)

    # ============================================================
    #  Callback progresso  ★ NUOVO
    # ============================================================

    def _cb_totale(self, val: float):
        self.progress_bar.set(val)
        n = len(self.items)
        done = round(val * n)
        self.lbl_totale.configure(text=f"Totale: {done} / {n} file")
        self.update_idletasks()

    def _cb_file(self, filename: str, val: float):
        self.lbl_file_corrente.configure(text=f"📄  {filename}")
        self.progress_file.set(val)
        self.update_idletasks()

    # ============================================================
    #  Esecuzione merge
    # ============================================================

    def esegui(self):
        # Mostra il contenitore di progresso
        self.progress_container.pack(
            fill="x", padx=18, pady=4, before=self.btn_avvia
        )
        self.progress_bar.set(0)
        self.progress_file.set(0)
        self.lbl_file_corrente.configure(text="Avvio...")
        self.lbl_totale.configure(text="")
        self.btn_avvia.configure(state="disabled")
        self.update()

        tasks = [item.get_data() for item in self.items]
        outputs: list = []
        errors: list = []

        try:
            outputs, errors = elabora_documento(
                tasks,
                manga_mode=self.style_var.get() == "Orientale",
                output_dir=Path(self.output_dir_var.get()),
                compress_preset=self.compress_var.get(),
                callback_totale=self._cb_totale,
                callback_file=self._cb_file,
            )
        except Exception as exc:
            CTkMessagebox(title="Errore critico", message=str(exc), icon="cancel")
        else:
            self._show_results(outputs, errors)
        finally:
            self.progress_container.pack_forget()
            self.btn_avvia.configure(state="normal")

    def _show_results(self, outputs: list, errors: list):
        output_dir = Path(self.output_dir_var.get())
        n_ok  = len(outputs)
        n_err = len(errors)

        if n_err == 0:
            # ★ Pulsante "Apri Cartella"
            dlg = CTkMessagebox(
                title="Completato",
                message=f"✅  {n_ok} file elaborati con successo!\n📂  {output_dir}",
                icon="check",
                option_1="Apri Cartella",
                option_2="OK",
            )
            if dlg.get() == "Apri Cartella":
                _open_in_file_manager(output_dir)

        elif n_ok == 0:
            CTkMessagebox(
                title="Errore",
                message=f"Tutti i {n_err} file hanno generato errori.\nControlla il log per i dettagli.",
                icon="cancel",
            )
            ErrorLogDialog(self, errors)

        else:
            dlg = CTkMessagebox(
                title="Completato con avvisi",
                message=(
                    f"✅  {n_ok} file elaborati correttamente\n"
                    f"⚠️   {n_err} file con errori\n"
                    f"📂  {output_dir}"
                ),
                icon="warning",
                option_1="Apri Cartella",
                option_2="Vedi Errori",
                option_3="OK",
            )
            choice = dlg.get()
            if choice == "Apri Cartella":
                _open_in_file_manager(output_dir)
            elif choice == "Vedi Errori":
                ErrorLogDialog(self, errors)
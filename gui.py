import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD
from CTkMessagebox import CTkMessagebox
from logic import elabora_documento
import os, fitz, sys, re, platform


def _get_tkdnd_subdir() -> str | None:
    """
    Restituisce la subdirectory corretta dei binari tkdnd
    in base al sistema operativo e all'architettura della CPU.
    """
    system = platform.system()
    machine = platform.machine().lower()

    if system == "Windows":
        return "win-x64" if sys.maxsize > 2**32 else "win-x86"
    elif system == "Darwin":
        # Apple Silicon (M1/M2/M3) o Intel
        return "osx-arm64" if machine == "arm64" else "osx-x86_64"
    elif system == "Linux":
        if "aarch64" in machine or "arm64" in machine:
            return "linux-aarch64"
        return "linux-x86_64" if sys.maxsize > 2**32 else "linux-x86"
    return None


def _parse_drop_paths(data: str) -> list[str]:
    """
    Parsa la stringa di drop di tkinterdnd2 in modo cross-platform.

    Il formato varia per sistema e per presenza di spazi nei path:
      - Path senza spazi:          /home/user/file.pdf
      - Path con spazi (brace):    {/home/user/mio file.pdf}
      - File multipli misti:       /path/a.pdf {/path/b c.pdf} /path/d.pdf
    """
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
            # Taglia al primo spazio; il resto rimane da processare
            space = current.find(" ")
            if space == -1:
                paths.append(current)
                break
            paths.append(current[:space])
            current = current[space:].strip()
    return paths


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


class PDFItem(ctk.CTkFrame):
    def __init__(self, master, file_path: str, on_remove, on_move_up, on_move_down):
        super().__init__(master)
        self.file_path = file_path
        self.exclusions = ""

        doc = fitz.open(file_path)
        self.max_pagine = len(doc)
        doc.close()

        is_single = self.max_pagine <= 1
        slider_to, steps = (1.1, 1) if is_single else (self.max_pagine, self.max_pagine - 1)

        # --- Header ---
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=10, pady=(5, 0))

        ctk.CTkLabel(
            self.header,
            text=os.path.basename(file_path),
            font=("Roboto", 12, "bold"),
            text_color="#2ecc71",
        ).pack(side="left")

        ctk.CTkLabel(
            self.header,
            text=f"  •  Numero pagine: {self.max_pagine}",
            font=("Roboto", 11),
            text_color="#95A5A6",
        ).pack(side="left")

        ctk.CTkButton(self.header, text="X", width=25, height=20, fg_color="#C0392B",
                      command=lambda: on_remove(self)).pack(side="right", padx=2)
        ctk.CTkButton(self.header, text="▼", width=25, height=20, fg_color="#34495E",
                      command=lambda: on_move_down(self)).pack(side="right", padx=2)
        ctk.CTkButton(self.header, text="▲", width=25, height=20, fg_color="#34495E",
                      command=lambda: on_move_up(self)).pack(side="right", padx=2)

        # Tasto tre puntini per le esclusioni
        self.btn_dots = ctk.CTkButton(
            self.header, text="...", width=30, height=20, fg_color="#5D6D7E",
            command=self.open_exclusion_dialog,
        )
        self.btn_dots.pack(side="right", padx=5)

        # --- Slider Inizio ---
        self.label_s = ctk.CTkLabel(self, text="Inizio: 1", font=("Roboto", 13, "bold"))
        self.label_s.pack(padx=20, anchor="w")
        self.slider_s = ctk.CTkSlider(self, from_=1, to=slider_to, number_of_steps=steps,
                                      height=18, command=self.update_labels)
        self.slider_s.set(1)
        self.slider_s.pack(fill="x", padx=20)

        # --- Slider Fine ---
        self.label_e = ctk.CTkLabel(self, text=f"Fine: {self.max_pagine}", font=("Roboto", 13, "bold"))
        self.label_e.pack(padx=20, anchor="w")
        self.slider_e = ctk.CTkSlider(self, from_=1, to=slider_to, number_of_steps=steps,
                                      height=18, command=self.update_labels)
        self.slider_e.set(self.max_pagine)
        self.slider_e.pack(fill="x", padx=20, pady=(0, 10))

        if is_single:
            self.slider_s.configure(state="disabled")
            self.slider_e.configure(state="disabled")

    def open_exclusion_dialog(self):
        dialog = ExclusionDialog(self.winfo_toplevel(), self.exclusions, self.max_pagine)
        self.master.wait_window(dialog)
        self.exclusions = dialog.result
        color = "#F39C12" if self.exclusions.strip() else "#5D6D7E"
        self.btn_dots.configure(fg_color=color)

    def parse_exclusions(self) -> set[int]:
        """Converte la stringa '1, 3-5' in un set di indici 0-based."""
        excluded: set[int] = set()
        for part in re.split(r"[,\s]+", self.exclusions):
            if "-" in part:
                try:
                    start, end = map(int, part.split("-"))
                    excluded.update(range(start - 1, end))
                except ValueError:
                    pass
            elif part.isdigit():
                excluded.add(int(part) - 1)
        return excluded

    def update_labels(self, _=None):
        s, e = int(self.slider_s.get()), int(self.slider_e.get())
        if s > e:
            self.slider_s.set(e)
            s = e
        self.label_s.configure(text=f"Inizio: {s}")
        self.label_e.configure(text=f"Fine: {e}")

    def get_data(self) -> dict:
        return {
            "path": self.file_path,
            "start": int(self.slider_s.get()) - 1,
            "end": int(self.slider_e.get()),
            "exclude": self.parse_exclusions(),
        }


class PDFPageMergerGUI(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self._inizializza_tkdnd()

        self.title("PDF Page Merger")
        self.geometry("700x650")

        self.items: list[PDFItem] = []
        self.crea_widget()
        self._bind_mouse_wheel(self)

    def _inizializza_tkdnd(self):
        """
        Inizializza tkdnd caricando la libreria nativa corretta
        per il sistema operativo e l'architettura in uso.
        """
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

    def _bind_mouse_wheel(self, widget):
        """Associa la rotella del mouse ricorsivamente su tutti i widget figli."""
        try:
            widget.bind("<MouseWheel>", self._on_mouse_wheel)
            widget.bind("<Button-4>", self._on_mouse_wheel)   # Linux scroll up
            widget.bind("<Button-5>", self._on_mouse_wheel)   # Linux scroll down
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_mouse_wheel(child)

    def _on_mouse_wheel(self, event):
        if not hasattr(self, "scroll_frame") or not self.items:
            return

        # Windows/macOS: event.delta (positivo = su, negativo = giù)
        # Linux:         event.num 4 = su, 5 = giù  (event.delta == 0)
        if event.delta != 0:
            direction = -1 if event.delta > 0 else 1
        else:
            direction = -1 if event.num == 4 else 1

        self.scroll_frame._parent_canvas.yview_scroll(direction, "units")

    def crea_widget(self):
        ctk.CTkLabel(self, text="📚 PDF Page Merger", font=("Roboto", 22, "bold")).pack(pady=15)

        self.style_var = ctk.StringVar(value="Orientale")
        ctk.CTkSegmentedButton(
            self, values=["Orientale", "Occidentale"], variable=self.style_var
        ).pack(pady=5)

        self.drop_frame = ctk.CTkFrame(self, height=80, border_width=2, border_color="#3b8ed0")
        self.drop_frame.pack(pady=10, padx=20, fill="x")
        self.drop_frame.pack_propagate(False)

        ctk.CTkLabel(self.drop_frame, text="Trascina qui i PDF").pack(expand=True)
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind("<<Drop>>", self.gestisci_drop)

        ctk.CTkButton(self, text="📁 Seleziona File", command=self.seleziona_file,
                      fg_color="#1b5e20", hover_color="#145A32", height=32).pack(pady=5)

        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Lista Documenti")

        self.progress_bar = ctk.CTkProgressBar(self)
        self.btn_avvia = ctk.CTkButton(
            self, text="MERGE PDF", command=self.esegui,
            state="disabled", font=("Roboto", 14, "bold"), height=40,
        )
        self.btn_avvia.pack(pady=15, side="bottom")

    def seleziona_file(self):
        paths = ctk.filedialog.askopenfilenames(filetypes=[("PDF Files", "*.pdf")])
        for p in paths:
            self.aggiungi_pdf(p)

    def gestisci_drop(self, event):
        """
        Gestisce il drag & drop in modo cross-platform.
        tkinterdnd2 usa le graffe per i path con spazi su tutti i SO.
        """
        for p in _parse_drop_paths(event.data):
            if p.lower().endswith(".pdf"):
                self.aggiungi_pdf(p)

    def aggiungi_pdf(self, path: str):
        if not self.items:
            self.scroll_frame.pack(pady=5, padx=20, fill="both", expand=True, before=self.btn_avvia)

        item = PDFItem(self.scroll_frame, path, self.rimuovi_pdf, self.muovi_su, self.muovi_giu)
        item.pack(fill="x", pady=5, padx=5)
        self.items.append(item)

        self._bind_mouse_wheel(item)
        self.btn_avvia.configure(state="normal")

    def rimuovi_pdf(self, item: PDFItem):
        item.destroy()
        self.items.remove(item)
        if not self.items:
            self.scroll_frame.pack_forget()
            self.btn_avvia.configure(state="disabled")

    def muovi_su(self, item: PDFItem):
        idx = self.items.index(item)
        if idx > 0:
            self.items[idx], self.items[idx - 1] = self.items[idx - 1], self.items[idx]
            self.refresh_list()

    def muovi_giu(self, item: PDFItem):
        idx = self.items.index(item)
        if idx < len(self.items) - 1:
            self.items[idx], self.items[idx + 1] = self.items[idx + 1], self.items[idx]
            self.refresh_list()

    def refresh_list(self):
        for item in self.items:
            item.pack_forget()
            item.pack(fill="x", pady=5, padx=5)

    def esegui(self):
        self.progress_bar.pack(pady=10, fill="x", padx=60, before=self.btn_avvia)
        self.btn_avvia.configure(state="disabled")
        self.update()

        tasks = [item.get_data() for item in self.items]
        try:
            elabora_documento(tasks, self.style_var.get() == "Orientale", self.progress_bar.set)
            CTkMessagebox(
                title="Successo",
                message="Operazione completata!\nI file sono nella cartella Documenti/pdf-page-merger",
                icon="check",
            )
        except Exception as e:
            CTkMessagebox(title="Errore", message=str(e), icon="cancel")
        finally:
            self.progress_bar.pack_forget()
            self.btn_avvia.configure(state="normal")
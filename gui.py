import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD
from CTkMessagebox import CTkMessagebox
from logic import elabora_documento
import os, fitz, sys

class PDFItem(ctk.CTkFrame):
    def __init__(self, master, file_path, on_remove, on_move_up, on_move_down):
        super().__init__(master)
        self.file_path = file_path
        doc = fitz.open(file_path); self.max_pagine = len(doc); doc.close()

        is_single = self.max_pagine <= 1
        slider_to, steps = (1.1, 1) if is_single else (self.max_pagine, self.max_pagine - 1)

        # Header
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=10, pady=(5, 0))
        ctk.CTkLabel(self.header, text=os.path.basename(file_path), font=("Roboto", 13, "bold"), text_color="#2ecc71").pack(side="left")
        ctk.CTkButton(self.header, text="X", width=30, height=25, fg_color="#C0392B", command=lambda: on_remove(self)).pack(side="right", padx=2)
        ctk.CTkButton(self.header, text="▼", width=30, height=25, fg_color="#34495E", command=lambda: on_move_down(self)).pack(side="right", padx=2)
        ctk.CTkButton(self.header, text="▲", width=30, height=25, fg_color="#34495E", command=lambda: on_move_up(self)).pack(side="right", padx=2)

        ctk.CTkLabel(self, text=f"Pagine: {self.max_pagine}", font=("Roboto", 10, "italic"), text_color="gray").pack(padx=10, anchor="w")

        # Slider Inizio/Fine
        self.label_s = ctk.CTkLabel(self, text="Inizio: 1")
        self.label_s.pack(padx=20, anchor="w")
        self.slider_s = ctk.CTkSlider(self, from_=1, to=slider_to, number_of_steps=steps, command=self.update_labels)
        self.slider_s.set(1); self.slider_s.pack(fill="x", padx=20)

        self.label_e = ctk.CTkLabel(self, text=f"Fine: {self.max_pagine}")
        self.label_e.pack(padx=20, anchor="w")
        self.slider_e = ctk.CTkSlider(self, from_=1, to=slider_to, number_of_steps=steps, command=self.update_labels)
        self.slider_e.set(self.max_pagine); self.slider_e.pack(fill="x", padx=20, pady=(0, 15))

        if is_single:
            self.slider_s.configure(state="disabled"); self.slider_e.configure(state="disabled")

    def update_labels(self, _=None):
        s, e = int(self.slider_s.get()), int(self.slider_e.get())
        s, e = min(s, self.max_pagine), min(e, self.max_pagine)
        if s > e: self.slider_s.set(e); s = e
        self.label_s.configure(text=f"Inizio: {s}"); self.label_e.configure(text=f"Fine: {e}")

    def get_data(self):
        return {"path": self.file_path, "start": int(min(self.slider_s.get(), self.max_pagine)) - 1, "end": int(min(self.slider_e.get(), self.max_pagine))}

class PDFMangaGUI(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self._inizializza_tkdnd()
        self.title("PDF Page Merger"); self.geometry("750x850")
        self.items = []
        self.crea_widget()

    def _inizializza_tkdnd(self):
        try:
            import tkinterdnd2
            path = os.path.join(os.path.dirname(tkinterdnd2.__file__), 'tkdnd', "win-x64" if sys.maxsize > 2**32 else "win-x86")
            self.tk.call('lappend', 'auto_path', path); self.tk.call('package', 'require', 'tkdnd')
        except: pass

    def crea_widget(self):
        ctk.CTkLabel(self, text="📚 PDF Page Merger", font=("Roboto", 24, "bold")).pack(pady=20)
        self.style_var = ctk.StringVar(value="Orientale")
        ctk.CTkSegmentedButton(self, values=["Orientale", "Occidentale"], variable=self.style_var).pack(pady=10)

        self.drop_frame = ctk.CTkFrame(self, height=100, border_width=2, border_color="#3b8ed0")
        self.drop_frame.pack(pady=10, padx=30, fill="x"); self.drop_frame.pack_propagate(False)
        ctk.CTkLabel(self.drop_frame, text="Trascina qui i PDF").pack(expand=True)
        self.drop_frame.drop_target_register(DND_FILES); self.drop_frame.dnd_bind('<<Drop>>', self.gestisci_drop)

        ctk.CTkButton(self, text="📁 Seleziona File", command=self.seleziona_file, fg_color="#1b5e20").pack(pady=10)
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Lista Documenti")
        self.progress_bar = ctk.CTkProgressBar(self)
        self.btn_avvia = ctk.CTkButton(self, text="MERGE PDF", command=self.esegui, state="disabled", font=("Roboto", 14, "bold"))
        self.btn_avvia.pack(pady=20, side="bottom")

    def seleziona_file(self):
        paths = ctk.filedialog.askopenfilenames(filetypes=[("PDF Files", "*.pdf")])
        if paths: 
            for p in paths: self.aggiungi_pdf(p)

    def gestisci_drop(self, event):
        paths = event.data.strip('{}').split('} {')
        for p in paths:
            if p.lower().endswith('.pdf'): self.aggiungi_pdf(p)

    def aggiungi_pdf(self, path):
        if not self.items: self.scroll_frame.pack(pady=10, padx=30, fill="both", expand=True, before=self.btn_avvia)
        item = PDFItem(self.scroll_frame, path, self.rimuovi_pdf, self.muovi_su, self.muovi_giu)
        item.pack(fill="x", pady=8, padx=5); self.items.append(item)
        self.btn_avvia.configure(state="normal")

    def rimuovi_pdf(self, item):
        item.destroy(); self.items.remove(item)
        if not self.items: self.scroll_frame.pack_forget(); self.btn_avvia.configure(state="disabled")

    def muovi_su(self, item):
        idx = self.items.index(item)
        if idx > 0: self.items[idx], self.items[idx-1] = self.items[idx-1], self.items[idx]; self.refresh_list()

    def muovi_giu(self, item):
        idx = self.items.index(item)
        if idx < len(self.items) - 1: self.items[idx], self.items[idx+1] = self.items[idx+1], self.items[idx]; self.refresh_list()

    def refresh_list(self):
        for item in self.items: item.pack_forget(); item.pack(fill="x", pady=8, padx=5)

    def esegui(self):
        self.progress_bar.pack(pady=10, fill="x", padx=60, before=self.btn_avvia)
        self.btn_avvia.configure(state="disabled"); self.update()
        tasks = [item.get_data() for item in self.items]
        try:
            out = elabora_documento(tasks, self.style_var.get() == "Orientale", self.progress_bar.set)
            CTkMessagebox(title="Successo", message=f"Creato in Documenti/pdf-page-merger:\n{out.name}", icon="check")
        except Exception as e: CTkMessagebox(title="Errore", message=str(e), icon="cancel")
        finally: self.progress_bar.pack_forget(); self.btn_avvia.configure(state="normal")
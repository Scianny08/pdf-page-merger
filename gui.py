import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD
from CTkMessagebox import CTkMessagebox
from logic import elabora_documento
import os
import fitz
import platform
import sys

class PDFMangaGUI(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        # Inizializzazione base di CTk
        super().__init__()
        
        self._inizializza_tkdnd()
        
        self.title("PDF Fusion")
        self.geometry("600x625")
        self.file_path = None
        self.crea_widget()

    def _inizializza_tkdnd(self):
        """Risolve il mismatch 32/64 bit caricando i binari corretti."""
        try:
            import tkinterdnd2
            base_dir = os.path.dirname(tkinterdnd2.__file__)
            
            # Determiniamo se Python è a 64 o 32 bit
            is_64bit = sys.maxsize > 2**32
            arch_dir = "win-x64" if is_64bit else "win-x86"
            
            # Costruiamo il percorso assoluto ai binari corretti
            tkdnd_binaries = os.path.join(base_dir, 'tkdnd', arch_dir)
            
            if os.path.exists(tkdnd_binaries):
                self.tk.call('lappend', 'auto_path', tkdnd_binaries)
                self.tk.call('package', 'require', 'tkdnd')
            else:
                print(f"DEBUG: Percorso binari non trovato: {tkdnd_binaries}")
        except Exception as e:
            print(f"CRITICAL: Fallimento inizializzazione TkDnD: {e}")

    def crea_widget(self):
        # Titolo Header
        ctk.CTkLabel(self, text="📚 PDF Fusion", font=("Roboto", 26, "bold")).pack(pady=20)

        # Selettore Stile
        style_frame = ctk.CTkFrame(self, fg_color="transparent")
        style_frame.pack(pady=10)
        ctk.CTkLabel(style_frame, text="Stile di affiancamento:", font=("Roboto", 13)).pack()
        
        self.style_var = ctk.StringVar(value="Manga")
        self.style_selector = ctk.CTkSegmentedButton(
            style_frame, 
            values=["Manga", "Occidentale"], 
            variable=self.style_var,
            width=280
        )
        self.style_selector.pack(pady=10)

        # Area Drag & Drop
        self.drop_frame = ctk.CTkFrame(self, width=520, height=130, border_width=2, border_color="#3b8ed0")
        self.drop_frame.pack(pady=10, padx=20, fill="x")
        self.drop_frame.pack_propagate(False)
        
        self.label_drop = ctk.CTkLabel(self.drop_frame, text="Trascina il PDF qui\n(o usa il tasto sotto)", font=("Roboto", 13))
        self.label_drop.pack(expand=True)
        
        # Registrazione sicura dei target
        try:
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind('<<Drop>>', self.gestisci_drop)
        except Exception as e:
            print(f"WARN: Drag & Drop non disponibile: {e}")
            self.label_drop.configure(text="Drag & Drop disabilitato (Errore Driver)")

        # Pulsante Importa (Verde scuro)
        self.btn_import = ctk.CTkButton(
            self, text="📁 Seleziona File Manualmente", 
            command=self.seleziona_file,
            fg_color="#145A32", hover_color="#0E3F23",
            font=("Roboto", 13, "bold"), height=35
        )
        self.btn_import.pack(pady=15)

        # Range Sliders
        slider_container = ctk.CTkFrame(self, fg_color="transparent")
        slider_container.pack(pady=10, padx=40, fill="x")

        self.label_start = ctk.CTkLabel(slider_container, text="Pagina Iniziale: 1")
        self.label_start.pack()
        self.slider_start = ctk.CTkSlider(slider_container, from_=1, to=100, command=self.valida_slider)
        self.slider_start.pack(pady=5, fill="x")

        self.label_end = ctk.CTkLabel(slider_container, text="Pagina Finale: 1")
        self.label_end.pack(pady=(10, 0))
        self.slider_end = ctk.CTkSlider(slider_container, from_=1, to=100, command=self.valida_slider)
        self.slider_end.pack(pady=5, fill="x")

        # Barra Progresso
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)

        # Bottone Action
        self.btn_avvia = ctk.CTkButton(
            self, text="ELABORA DOCUMENTO", command=self.esegui,
            state="disabled", height=45, font=("Roboto", 14, "bold"),
            fg_color="#3b8ed0", hover_color="#2d6da3"
        )
        self.btn_avvia.pack(pady=30)

    def valida_slider(self, _=None):
        s, e = int(self.slider_start.get()), int(self.slider_end.get())
        if s > e:
            self.slider_start.set(e)
            s = e
        self.label_start.configure(text=f"Inizio Range: {s}")
        self.label_end.configure(text=f"Fine Range: {e}")

    def carica_info_pdf(self, path):
        try:
            self.file_path = path
            doc = fitz.open(path)
            total = len(doc)
            doc.close()
            
            self.slider_start.configure(from_=1, to=total, number_of_steps=total-1)
            self.slider_end.configure(from_=1, to=total, number_of_steps=total-1)
            self.slider_start.set(1)
            self.slider_end.set(total)
            self.valida_slider()
            
            self.btn_avvia.configure(state="normal")
            self.label_drop.configure(text=f"✅ {os.path.basename(path)} caricato", text_color="#2ecc71")
        except Exception as e:
            CTkMessagebox(title="Errore", message=f"PDF non valido: {e}", icon="cancel")

    def seleziona_file(self):
        path = ctk.filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if path: self.carica_info_pdf(path)

    def gestisci_drop(self, event):
        path = event.data.strip('{}')
        if path.lower().endswith('.pdf'): self.carica_info_pdf(path)

    def esegui(self):
        self.btn_avvia.configure(state="disabled")
        self.progress_bar.pack(pady=10, padx=60, fill="x", before=self.btn_avvia)
        self.update()
        
        try:
            mode = self.style_var.get() == "Manga"
            out = elabora_documento(
                self.file_path, 
                int(self.slider_start.get()) - 1, 
                int(self.slider_end.get()), 
                manga_mode=mode, 
                callback_progresso=self.progress_bar.set
            )
            CTkMessagebox(title="Completato", message=f"Output generato:\n{out.name}", icon="check")
        except Exception as err:
            CTkMessagebox(title="Errore logico", message=str(err), icon="cancel")
        finally:
            self.progress_bar.pack_forget()
            self.btn_avvia.configure(state="normal")
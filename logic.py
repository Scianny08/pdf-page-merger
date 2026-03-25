import fitz  # PyMuPDF
import platform
import subprocess
from pathlib import Path


def get_documents_path() -> Path:
    """
    Restituisce il percorso della cartella Documenti dell'utente
    in modo affidabile su Windows, macOS e Linux.
    """
    home = Path.home()
    system = platform.system()

    if system == "Windows":
        # Prima scelta: registro di sistema (gestisce percorsi personalizzati
        # e OneDrive redirect correttamente)
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            )
            path, _ = winreg.QueryValueEx(key, "Personal")
            winreg.CloseKey(key)
            p = Path(path)
            if p.exists():
                return p
        except Exception:
            pass
        # Fallback: percorso standard Windows
        return home / "Documents"

    elif system == "Darwin":
        # Su macOS ~/Documents è sempre il percorso standard,
        # non c'è un equivalente di xdg-user-dir
        docs = home / "Documents"
        return docs if docs.exists() else home

    else:
        # Linux: xdg-user-dir è lo standard freedesktop
        try:
            result = subprocess.run(
                ["xdg-user-dir", "DOCUMENTS"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                p = Path(result.stdout.strip())
                # xdg-user-dir restituisce $HOME se la cartella non è configurata:
                # in quel caso usiamo il fallback sotto
                if p.exists() and p != home:
                    return p
        except Exception:
            pass
        # Fallback: nomi comuni nelle distribuzioni con varie lingue
        for folder in ("Documents", "Documenti", "Documentos"):
            if (home / folder).exists():
                return home / folder
        return home


def elabora_documento(lista_task: list[dict], manga_mode: bool = True,
                      callback_progresso=None) -> Path | None:
    """
    Elabora ogni PDF separatamente applicando l'affiancamento e le esclusioni.
    Restituisce il path dell'ultimo file salvato.
    """
    totale_file = len(lista_task)
    output_dir = get_documents_path() / "pdf-page-merger"
    output_dir.mkdir(parents=True, exist_ok=True)

    ultimo_output = None

    for idx, task in enumerate(lista_task):
        pdf_writer = fitz.open()

        path = task["path"]
        start = task["start"]
        end = task["end"]
        excluded: set[int] = task.get("exclude", set())

        current_file = Path(path)
        doc = fitz.open(path)

        # --- 1. Pagine singole pre-range (es. copertina) ---
        for p in range(0, start):
            if p not in excluded and p < len(doc):
                pdf_writer.insert_pdf(doc, from_page=p, to_page=p)

        # --- 2. Pagine affiancate nel range selezionato ---
        pagine_valide = [
            p for p in range(start, end)
            if p not in excluded and p < len(doc)
        ]

        i = 0
        while i < len(pagine_valide):
            idx_1 = pagine_valide[i]

            if i + 1 < len(pagine_valide):
                idx_2 = pagine_valide[i + 1]
                p1, p2 = doc[idx_1], doc[idx_2]

                nw = p1.rect.width + p2.rect.width
                nh = max(p1.rect.height, p2.rect.height)
                new_page = pdf_writer.new_page(width=nw, height=nh)

                if manga_mode:  # Orientale: DX → SX
                    new_page.show_pdf_page(fitz.Rect(0, 0, p2.rect.width, p2.rect.height), doc, idx_2)
                    new_page.show_pdf_page(fitz.Rect(p2.rect.width, 0, nw, p1.rect.height), doc, idx_1)
                else:           # Occidentale: SX → DX
                    new_page.show_pdf_page(fitz.Rect(0, 0, p1.rect.width, p1.rect.height), doc, idx_1)
                    new_page.show_pdf_page(fitz.Rect(p1.rect.width, 0, nw, p2.rect.height), doc, idx_2)
                i += 2
            else:
                # Pagina dispari rimasta: inserita singola
                pdf_writer.insert_pdf(doc, from_page=idx_1, to_page=idx_1)
                i += 1

        # --- 3. Pagine singole post-range (es. extra/crediti) ---
        for p in range(end, len(doc)):
            if p not in excluded:
                pdf_writer.insert_pdf(doc, from_page=p, to_page=p)

        # --- Salvataggio ---
        suffisso = "ORIENTALE" if manga_mode else "OCCIDENTALE"
        output_path = output_dir / f"{current_file.stem} - {suffisso}.pdf"

        pdf_writer.save(str(output_path))
        pdf_writer.close()
        doc.close()

        ultimo_output = output_path

        if callback_progresso:
            callback_progresso((idx + 1) / totale_file)

    return ultimo_output
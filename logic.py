import fitz  # PyMuPDF
from pathlib import Path
from datetime import datetime
import os

def get_documents_path():
    """Ritorna il percorso Documenti cross-platform (Win/Mac/Linux)."""
    home = Path.home()
    
    # Su Linux, prova a leggere la configurazione standard delle cartelle utente
    xdg_docs = os.popen('xdg-user-dir DOCUMENTS').read().strip()
    if xdg_docs and os.path.exists(xdg_docs):
        return Path(xdg_docs)
    
    # Fallback manuali per sistemi non-XDG o localizzati
    for folder in ["Documents", "Documenti", "Documentos", "Documents"]:
        if (home / folder).exists():
            return home / folder
            
    return home  # Ultima spiaggia: la Home dell'utente

def elabora_documento(lista_task, manga_mode=True, callback_progresso=None):
    pdf_writer = fitz.open()
    totale_file = len(lista_task)
    
    for idx, task in enumerate(lista_task):
        path = task['path']
        start, end = task['start'], task['end']
        doc = fitz.open(path)
        
        # 1. Pagine prima del range
        if start > 0:
            pdf_writer.insert_pdf(doc, from_page=0, to_page=start-1)

        # 2. Pagine nel range (Affiancate)
        pagine_range = list(range(start, end))
        i = 0
        while i < len(pagine_range):
            idx_1 = pagine_range[i]
            if i + 1 < len(pagine_range):
                idx_2 = pagine_range[i + 1]
                p1, p2 = doc[idx_1], doc[idx_2]
                new_w, new_h = p1.rect.width + p2.rect.width, max(p1.rect.height, p2.rect.height)
                new_page = pdf_writer.new_page(width=new_w, height=new_h)
                
                if manga_mode: # ORIENTALE
                    new_page.show_pdf_page(fitz.Rect(0, 0, p2.rect.width, p2.rect.height), doc, idx_2)
                    new_page.show_pdf_page(fitz.Rect(p2.rect.width, 0, new_w, p1.rect.height), doc, idx_1)
                else: # OCCIDENTALE
                    new_page.show_pdf_page(fitz.Rect(0, 0, p1.rect.width, p1.rect.height), doc, idx_1)
                    new_page.show_pdf_page(fitz.Rect(p1.rect.width, 0, new_w, p2.rect.height), doc, idx_2)
                i += 2
            else:
                pdf_writer.insert_pdf(doc, from_page=idx_1, to_page=idx_1)
                i += 1
        
        # 3. Pagine dopo il range
        if end < len(doc):
            pdf_writer.insert_pdf(doc, from_page=end, to_page=len(doc)-1)
            
        doc.close()
        if callback_progresso: callback_progresso((idx + 1) / totale_file)

    # --- SALVATAGGIO IN DOCUMENTI/PDF-PAGE-MERGER ---
    output_dir = get_documents_path() / "pdf-page-merger"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    primo_file_path = Path(lista_task[0]['path'])
    suffisso = "- ORIENTALE" if manga_mode else "- OCCIDENTALE"
    output_path = output_dir / f"{primo_file_path.stem} {suffisso}.pdf"
    
    pdf_writer.save(str(output_path))
    pdf_writer.close()
    return output_path
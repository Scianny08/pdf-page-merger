import fitz  # PyMuPDF
from pathlib import Path
import os

def get_documents_path():
    """Ritorna il percorso Documenti cross-platform."""
    home = Path.home()
    try:
        xdg_docs = os.popen('xdg-user-dir DOCUMENTS').read().strip()
        if xdg_docs and os.path.exists(xdg_docs): return Path(xdg_docs)
    except: pass
    
    for folder in ["Documents", "Documenti", "Documentos"]:
        if (home / folder).exists(): return home / folder
    return home

def elabora_documento(lista_task, manga_mode=True, callback_progresso=None):
    """
    Elabora ogni file della lista separatamente e salva file distinti.
    """
    totale_file = len(lista_task)
    output_dir = get_documents_path() / "pdf-page-merger"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    ultimo_output = None

    for idx, task in enumerate(lista_task):
        # --- RESET PER OGNI FILE ---
        # Creiamo un nuovo documento PDF vuoto per ogni task nella lista
        pdf_writer = fitz.open() 
        
        path, start, end = task['path'], task['start'], task['end']
        current_file = Path(path)
        doc = fitz.open(path)
        
        # 1. Pagine singole pre-range
        if start > 0:
            pdf_writer.insert_pdf(doc, from_page=0, to_page=start-1)
            
        # 2. Elaborazione pagine affiancate nel range
        pagine_range = list(range(start, end))
        i = 0
        while i < len(pagine_range):
            idx_1 = pagine_range[i]
            if i + 1 < len(pagine_range):
                idx_2 = pagine_range[i + 1]
                p1, p2 = doc[idx_1], doc[idx_2]
                nw, nh = p1.rect.width + p2.rect.width, max(p1.rect.height, p2.rect.height)
                new_page = pdf_writer.new_page(width=nw, height=nh)
                
                if manga_mode: # ORIENTALE
                    new_page.show_pdf_page(fitz.Rect(0, 0, p2.rect.width, p2.rect.height), doc, idx_2)
                    new_page.show_pdf_page(fitz.Rect(p2.rect.width, 0, nw, p1.rect.height), doc, idx_1)
                else: # OCCIDENTALE
                    new_page.show_pdf_page(fitz.Rect(0, 0, p1.rect.width, p1.rect.height), doc, idx_1)
                    new_page.show_pdf_page(fitz.Rect(p1.rect.width, 0, nw, p2.rect.height), doc, idx_2)
                i += 2
            else:
                pdf_writer.insert_pdf(doc, from_page=idx_1, to_page=idx_1)
                i += 1
                
        # 3. Pagine singole post-range
        if end < len(doc):
            pdf_writer.insert_pdf(doc, from_page=end, to_page=len(doc)-1)
            
        # --- SALVATAGGIO SINGOLO FILE ---
        suffisso = "- ORIENTALE" if manga_mode else "- OCCIDENTALE"
        nome_file_output = f"{current_file.stem} {suffisso}.pdf"
        output_path = output_dir / nome_file_output
        
        pdf_writer.save(str(output_path))
        pdf_writer.close()
        doc.close()
        
        ultimo_output = output_path
        
        if callback_progresso:
            callback_progresso((idx + 1) / totale_file)

    return ultimo_output # Ritorna l'ultimo per il messaggio di conferma
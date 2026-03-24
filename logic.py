import fitz  # PyMuPDF
from pathlib import Path

def elabora_documento(percorso_input, start_page, end_page, manga_mode=True, callback_progresso=None):
    doc = fitz.open(percorso_input)
    pdf_writer = fitz.open()
    totale_doc = len(doc)
    
    # 1. Pagine prima del range (Singole)
    for i in range(0, start_page):
        page = doc[i]
        new_page = pdf_writer.new_page(width=page.rect.width, height=page.rect.height)
        new_page.show_pdf_page(page.rect, doc, i)

    # 2. Pagine nel range (Affiancate)
    pagine_range = list(range(start_page, end_page))
    i = 0
    while i < len(pagine_range):
        idx_1 = pagine_range[i] # Prima pagina del PDF
        
        if i + 1 < len(pagine_range):
            idx_2 = pagine_range[i + 1] # Seconda pagina del PDF
            p1, p2 = doc[idx_1], doc[idx_2]
            
            new_w = p1.rect.width + p2.rect.width
            new_h = max(p1.rect.height, p2.rect.height)
            new_page = pdf_writer.new_page(width=new_w, height=new_h)
            
            if manga_mode:
                # STILE MANGA: idx_1 a DESTRA, idx_2 a SINISTRA
                new_page.show_pdf_page(fitz.Rect(0, 0, p2.rect.width, p2.rect.height), doc, idx_2)
                new_page.show_pdf_page(fitz.Rect(p2.rect.width, 0, new_w, p1.rect.height), doc, idx_1)
            else:
                # STILE OCCIDENTALE: idx_1 a SINISTRA, idx_2 a DESTRA
                new_page.show_pdf_page(fitz.Rect(0, 0, p1.rect.width, p1.rect.height), doc, idx_1)
                new_page.show_pdf_page(fitz.Rect(p1.rect.width, 0, new_w, p2.rect.height), doc, idx_2)
            i += 2
        else:
            # Pagina singola rimasta nel range
            page = doc[idx_1]
            new_page = pdf_writer.new_page(width=page.rect.width, height=page.rect.height)
            new_page.show_pdf_page(page.rect, doc, idx_1)
            i += 1
        
        if callback_progresso:
            callback_progresso(i / len(pagine_range))

    # 3. Pagine dopo il range (Singole)
    for i in range(end_page, totale_doc):
        page = doc[i]
        new_page = pdf_writer.new_page(width=page.rect.width, height=page.rect.height)
        new_page.show_pdf_page(page.rect, doc, i)

    suffix = "manga" if manga_mode else "occidentale"
    output_path = Path(percorso_input).parent / f"{Path(percorso_input).stem}_{suffix}.pdf"
    pdf_writer.save(str(output_path))
    pdf_writer.close()
    doc.close()
    return output_path
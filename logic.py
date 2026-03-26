import fitz  # PyMuPDF
import platform
import subprocess
from pathlib import Path
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Compressione
# ---------------------------------------------------------------------------

COMPRESS_PRESETS: dict[str, dict] = {
    "Nessuna": dict(deflate=False, garbage=0, clean=False),
    "Media":   dict(deflate=True,  garbage=2, clean=False,
                    deflate_images=True, deflate_fonts=True),
    "Alta":    dict(deflate=True,  garbage=4, clean=True,
                    deflate_images=True, deflate_fonts=True),
}


# ---------------------------------------------------------------------------
# Cartella Documenti (cross-platform)
# ---------------------------------------------------------------------------

def get_documents_path() -> Path:
    """
    Restituisce il percorso della cartella Documenti dell'utente
    in modo affidabile su Windows, macOS e Linux.
    """
    home = Path.home()
    system = platform.system()

    if system == "Windows":
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
        return home / "Documents"

    elif system == "Darwin":
        docs = home / "Documents"
        return docs if docs.exists() else home

    else:  # Linux
        try:
            result = subprocess.run(
                ["xdg-user-dir", "DOCUMENTS"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                p = Path(result.stdout.strip())
                if p.exists() and p != home:
                    return p
        except Exception:
            pass
        for folder in ("Documents", "Documenti", "Documentos"):
            if (home / folder).exists():
                return home / folder
        return home


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def elabora_documento(
    lista_task: list[dict],
    manga_mode: bool = True,
    output_dir: Optional[Path] = None,
    compress_preset: str = "Media",
    callback_totale: Optional[Callable[[float], None]] = None,
    callback_file: Optional[Callable[[str, float], None]] = None,
) -> tuple[list[Path], list[tuple[str, str]]]:
    """
    Elabora ogni PDF separatamente applicando l'affiancamento e le esclusioni.

    Parametri
    ---------
    lista_task       : lista di dizionari con chiavi path, start, end, exclude,
                       cover_alone
    manga_mode       : True = Orientale (DX→SX), False = Occidentale (SX→DX)
    output_dir       : cartella di output; se None usa Documenti/pdf-page-merger
    compress_preset  : "Nessuna" | "Media" | "Alta"
    callback_totale  : chiamata con progresso globale [0.0 – 1.0]
    callback_file    : chiamata con (nome_file, progresso_file [0.0 – 1.0])

    Restituisce
    -----------
    (lista_output, lista_errori)
    lista_errori : [(nome_file, messaggio_errore), …]
    """
    if output_dir is None:
        output_dir = get_documents_path() / "pdf-page-merger"
    output_dir.mkdir(parents=True, exist_ok=True)

    compress_opts = COMPRESS_PRESETS.get(compress_preset, COMPRESS_PRESETS["Media"])
    outputs: list[Path] = []
    errors: list[tuple[str, str]] = []
    n_task = len(lista_task)

    for idx, task in enumerate(lista_task):
        nome_file = Path(task["path"]).name

        # Notifica inizio file
        if callback_file:
            callback_file(nome_file, 0.0)

        try:
            # Closure per trasmettere il nome file al callback interno
            _cb: Optional[Callable[[float], None]] = None
            if callback_file:
                def _cb(p: float, _nf: str = nome_file) -> None:  # noqa: E731
                    callback_file(_nf, p)

            out = _elabora_singolo(task, manga_mode, output_dir, compress_opts, _cb)
            outputs.append(out)

        except Exception as exc:
            errors.append((nome_file, str(exc)))

        if callback_totale:
            callback_totale((idx + 1) / n_task)

    return outputs, errors


# ---------------------------------------------------------------------------
# Implementazione interna
# ---------------------------------------------------------------------------

def _elabora_singolo(
    task: dict,
    manga_mode: bool,
    output_dir: Path,
    compress_opts: dict,
    callback_file: Optional[Callable[[float], None]] = None,
) -> Path:
    path: str = task["path"]
    start: int = task["start"]
    end: int = task["end"]
    excluded: set[int] = task.get("exclude", set())
    cover_alone: bool = task.get("cover_alone", False)

    current_file = Path(path)
    doc = fitz.open(path)
    n = len(doc)
    pdf_writer = fitz.open()

    # ------------------------------------------------------------------
    # 1. Copertina singola (se richiesta e start == 0)
    # ------------------------------------------------------------------
    range_start = start
    if cover_alone and start == 0 and n > 0 and 0 not in excluded:
        pdf_writer.insert_pdf(doc, from_page=0, to_page=0)
        range_start = 1  # il merge inizia da pagina 1

    # ------------------------------------------------------------------
    # 2. Pagine singole pre-range
    # ------------------------------------------------------------------
    pre_first = 1 if (cover_alone and start == 0) else 0
    for p in range(pre_first, start):
        if p not in excluded and p < n:
            pdf_writer.insert_pdf(doc, from_page=p, to_page=p)

    # ------------------------------------------------------------------
    # 3. Pagine affiancate nel range selezionato
    # ------------------------------------------------------------------
    pagine_valide = [
        p for p in range(range_start, end)
        if p not in excluded and p < n
    ]

    totale_merge = max(len(pagine_valide), 1)
    processate = 0
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
                new_page.show_pdf_page(
                    fitz.Rect(0, 0, p2.rect.width, p2.rect.height), doc, idx_2)
                new_page.show_pdf_page(
                    fitz.Rect(p2.rect.width, 0, nw, p1.rect.height), doc, idx_1)
            else:           # Occidentale: SX → DX
                new_page.show_pdf_page(
                    fitz.Rect(0, 0, p1.rect.width, p1.rect.height), doc, idx_1)
                new_page.show_pdf_page(
                    fitz.Rect(p1.rect.width, 0, nw, p2.rect.height), doc, idx_2)

            processate += 2
            i += 2
        else:
            # Pagina dispari rimasta: inserita singola
            pdf_writer.insert_pdf(doc, from_page=idx_1, to_page=idx_1)
            processate += 1
            i += 1

        if callback_file:
            callback_file(min(processate / totale_merge, 1.0))

    # ------------------------------------------------------------------
    # 4. Pagine singole post-range
    # ------------------------------------------------------------------
    for p in range(end, n):
        if p not in excluded:
            pdf_writer.insert_pdf(doc, from_page=p, to_page=p)

    # ------------------------------------------------------------------
    # 5. Salvataggio con la compressione scelta
    # ------------------------------------------------------------------
    suffisso = "ORIENTALE" if manga_mode else "OCCIDENTALE"
    output_path = output_dir / f"{current_file.stem} - {suffisso}.pdf"
    pdf_writer.save(str(output_path), **compress_opts)
    pdf_writer.close()
    doc.close()

    return output_path
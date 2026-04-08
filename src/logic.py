"""
logic.py — Core PDF merging engine.

Responsibilities:
  - Locate the user's Documents folder (cross-platform)
  - Apply per-file page pairing (Eastern / Western layout)
  - Handle cover-alone, pre/post-range pages, and per-page exclusions
  - Save output with the selected compression preset
  - Collect errors per file so the GUI can continue the batch
"""

import fitz  # PyMuPDF
import platform
import subprocess
from pathlib import Path
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Compression presets
# Keys are shown directly in the GUI combo-box, so keep them readable.
# ---------------------------------------------------------------------------

COMPRESS_PRESETS: dict[str, dict] = {
    "None":   dict(deflate=False, garbage=0, clean=False),
    "Medium": dict(deflate=True,  garbage=2, clean=False,
                   deflate_images=True, deflate_fonts=True),
    "High":   dict(deflate=True,  garbage=4, clean=True,
                   deflate_images=True, deflate_fonts=True),
}


# ---------------------------------------------------------------------------
# Cross-platform Documents folder
# ---------------------------------------------------------------------------

def get_documents_path() -> Path:
    """
    Return the user's Documents folder reliably on Windows, macOS, and Linux.

    Windows  : reads the registry Shell Folders key so OneDrive redirects
               are honoured; falls back to ~/Documents.
    macOS    : ~/Documents is the canonical path; falls back to ~.
    Linux    : tries xdg-user-dir DOCUMENTS; falls back to common folder
               names in various locales, then ~.
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
            candidate = Path(path)
            if candidate.exists():
                return candidate
        except Exception:
            pass
        return home / "Documents"

    elif system == "Darwin":
        docs = home / "Documents"
        return docs if docs.exists() else home

    else:  # Linux / BSD
        try:
            result = subprocess.run(
                ["xdg-user-dir", "DOCUMENTS"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                candidate = Path(result.stdout.strip())
                # xdg-user-dir returns $HOME when the key is not configured
                if candidate.exists() and candidate != home:
                    return candidate
        except Exception:
            pass
        # Fallback: common locale-specific folder names
        for folder_name in ("Documents", "Documenti", "Documentos"):
            candidate = home / folder_name
            if candidate.exists():
                return candidate
        return home


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def elabora_documento(
    lista_task: list[dict],
    manga_mode: bool = True,
    output_dir: Optional[Path] = None,
    compress_preset: str = "Medium",
    callback_totale: Optional[Callable[[float], None]] = None,
    callback_file: Optional[Callable[[str, float], None]] = None,
) -> tuple[list[Path], list[tuple[str, str]]]:
    """
    Process each PDF independently, applying side-by-side page merging.

    Parameters
    ----------
    lista_task
        List of task dicts, each containing:
          path        : absolute path to the source PDF
          start       : 0-based first page of the merge range
          end         : 0-based exclusive last page of the merge range
          exclude     : set of 0-based page indices to skip entirely
          cover_alone : if True, page 0 is always kept as a single page
    manga_mode
        True  -> Eastern layout (right-to-left; page N+1 on visual left)
        False -> Western layout (left-to-right; page N on visual left)
    output_dir
        Destination folder; defaults to Documents/pdf-page-merger.
    compress_preset
        One of the COMPRESS_PRESETS keys: "None" | "Medium" | "High".
    callback_totale
        Called with a float in [0.0, 1.0] after each file completes.
    callback_file
        Called with (filename: str, progress: float) during page rendering
        of the current file.

    Returns
    -------
    (outputs, errors)
        outputs : list of Path objects for successfully saved files.
        errors  : list of (filename, error_message) tuples for failed files.
    """
    # Resolve output directory
    if output_dir is None:
        output_dir = get_documents_path() / "pdf-page-merger"
    output_dir.mkdir(parents=True, exist_ok=True)

    compress_opts = COMPRESS_PRESETS.get(compress_preset, COMPRESS_PRESETS["Medium"])
    outputs: list[Path] = []
    errors: list[tuple[str, str]] = []
    n_task = len(lista_task)

    for task_idx, task in enumerate(lista_task):
        file_name = Path(task["path"]).name

        # Signal the start of this file to the GUI
        if callback_file:
            callback_file(file_name, 0.0)

        try:
            # Build a per-file progress callback that carries the filename
            inner_cb: Optional[Callable[[float], None]] = None
            if callback_file:
                def inner_cb(
                    progress: float,
                    _name: str = file_name,
                ) -> None:
                    callback_file(_name, progress)

            output_path = _process_single_file(
                task, manga_mode, output_dir, compress_opts, inner_cb
            )
            outputs.append(output_path)

        except Exception as exc:
            # Record the error and continue — do not abort the entire batch
            errors.append((file_name, str(exc)))

        # Update overall progress regardless of success / failure
        if callback_totale:
            callback_totale((task_idx + 1) / n_task)

    return outputs, errors


# ---------------------------------------------------------------------------
# Internal implementation
# ---------------------------------------------------------------------------

def _process_single_file(
    task: dict,
    manga_mode: bool,
    output_dir: Path,
    compress_opts: dict,
    callback_file: Optional[Callable[[float], None]] = None,
) -> Path:
    """
    Build and save the merged PDF for a single source file.

    Page pipeline
    -------------
    1. Cover page (optional)  — page 0 kept as a single when cover_alone=True.
    2. Pre-range singles      — pages before `start` that are not excluded.
    3. Paired range           — pages [range_start, end) paired two-by-two;
                                an odd page-out is inserted as a single.
    4. Post-range singles     — pages from `end` to EOF that are not excluded.
    5. Save                   — write the output PDF with the chosen compression.
    """
    source_path:  str  = task["path"]
    start:        int  = task["start"]
    end:          int  = task["end"]
    excluded:     set  = task.get("exclude", set())
    keep_single:  set  = task.get("keep_single", set())   # present but never paired
    cover_alone:  bool = task.get("cover_alone", False)

    source_file = Path(source_path)
    doc         = fitz.open(source_path)
    total_pages = len(doc)
    writer      = fitz.open()   # empty output document

    # ------------------------------------------------------------------
    # 1. Cover page — always a single spread, never paired
    # ------------------------------------------------------------------
    range_start = start   # may advance to 1 when cover consumes page 0
    if cover_alone and start == 0 and total_pages > 0 and 0 not in excluded:
        writer.insert_pdf(doc, from_page=0, to_page=0)
        range_start = 1

    # ------------------------------------------------------------------
    # 2. Pre-range single pages
    # ------------------------------------------------------------------
    pre_loop_start = 1 if (cover_alone and start == 0) else 0
    for page_idx in range(pre_loop_start, start):
        if page_idx not in excluded and page_idx < total_pages:
            writer.insert_pdf(doc, from_page=page_idx, to_page=page_idx)

    # ------------------------------------------------------------------
    # 3. Paired pages inside the selected range
    #
    # valid_pages contains every non-excluded page in [range_start, end).
    # Pages that appear in keep_single are present in valid_pages but act
    # as "pairing barriers": they are inserted alone and prevent the
    # adjacent page from forming a spread with them.
    #
    # Pairing rules (evaluated top-to-bottom for the current slot):
    #   a) current page is keep_single                → insert alone, advance 1
    #   b) next page is keep_single (or does not exist) → insert current alone,
    #                                                      advance 1
    #   c) otherwise                                  → two-page spread, advance 2
    # ------------------------------------------------------------------
    valid_pages     = [
        p for p in range(range_start, end)
        if p not in excluded and p < total_pages
    ]
    total_to_process = max(len(valid_pages), 1)
    pages_processed  = 0
    pair_index       = 0

    while pair_index < len(valid_pages):
        left_doc_idx  = valid_pages[pair_index]
        left_is_single = left_doc_idx in keep_single

        # Determine whether a right neighbour exists and is pairable
        has_right        = pair_index + 1 < len(valid_pages)
        right_doc_idx    = valid_pages[pair_index + 1] if has_right else -1
        right_is_single  = has_right and (right_doc_idx in keep_single)

        can_pair = has_right and not left_is_single and not right_is_single

        if can_pair:
            # ---- Two-page spread ----------------------------------------
            page_l = doc[left_doc_idx]
            page_r = doc[right_doc_idx]

            spread_w = page_l.rect.width + page_r.rect.width
            spread_h = max(page_l.rect.height, page_r.rect.height)
            new_page = writer.new_page(width=spread_w, height=spread_h)

            if manga_mode:
                # Eastern: page N+1 on the visual LEFT, page N on the RIGHT
                new_page.show_pdf_page(
                    fitz.Rect(0, 0, page_r.rect.width, page_r.rect.height),
                    doc, right_doc_idx,
                )
                new_page.show_pdf_page(
                    fitz.Rect(page_r.rect.width, 0, spread_w, page_l.rect.height),
                    doc, left_doc_idx,
                )
            else:
                # Western: page N on the visual LEFT, page N+1 on the RIGHT
                new_page.show_pdf_page(
                    fitz.Rect(0, 0, page_l.rect.width, page_l.rect.height),
                    doc, left_doc_idx,
                )
                new_page.show_pdf_page(
                    fitz.Rect(page_l.rect.width, 0, spread_w, page_r.rect.height),
                    doc, right_doc_idx,
                )

            pages_processed += 2
            pair_index       += 2

        else:
            # ---- Single page (keep_single barrier, odd page-out, or
            #      right neighbour is itself a keep_single barrier) -------
            writer.insert_pdf(doc, from_page=left_doc_idx, to_page=left_doc_idx)
            pages_processed += 1
            pair_index       += 1

        # Report internal progress after every spread / single insertion
        if callback_file:
            callback_file(min(pages_processed / total_to_process, 1.0))

    # ------------------------------------------------------------------
    # 4. Post-range single pages
    # ------------------------------------------------------------------
    for page_idx in range(end, total_pages):
        if page_idx not in excluded:
            writer.insert_pdf(doc, from_page=page_idx, to_page=page_idx)

    # ------------------------------------------------------------------
    # 5. Save with the selected compression preset
    # ------------------------------------------------------------------
    layout_suffix = "EASTERN" if manga_mode else "WESTERN"
    output_path   = output_dir / f"{source_file.stem} - {layout_suffix}.pdf"
    writer.save(str(output_path), **compress_opts)
    writer.close()
    doc.close()

    return output_path
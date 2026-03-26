"""
gui.py — CustomTkinter frontend for PDF Page Merger.

Features implemented here:
  - Drag-and-drop file loading (cross-platform, tkinterdnd2)
  - Drag-to-reorder list items via a drag handle
  - Undo / Redo with Ctrl+Z / Ctrl+Y keyboard shortcuts
  - Per-file page-range sliders and cover-alone checkbox
  - Page exclusion dialog (label: "Enter page ranges to REMOVE")
  - Paginated merge preview: mouse-wheel and arrow-key navigation
  - Duplicate-file detection
  - Output-folder selector
  - Output compression selector
  - Dual progress bars (per-file + overall batch)
  - Error log dialog for partial failures
  - Open-folder shortcut in the success dialog
  - Light / Dark theme toggle (solid button, no emoji)

No `break` statements are used anywhere in this module.
"""

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD
from CTkMessagebox import CTkMessagebox
from logic import elabora_documento, get_documents_path, COMPRESS_PRESETS
from PIL import Image
import os, fitz, sys, re, platform, io, subprocess
from pathlib import Path


# ============================================================
#  Cross-platform helpers
# ============================================================

def _get_tkdnd_subdir() -> "str | None":
    """
    Return the platform-specific sub-directory that holds the native
    tkdnd shared library bundled with tkinterdnd2.
    """
    system  = platform.system()
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
    """
    Parse the tkinterdnd2 drop-event string into a plain list of file paths.

    Format notes (all platforms):
      - Paths without spaces : /home/user/file.pdf
      - Paths with spaces     : {/home/user/my file.pdf}
      - Mixed multiple paths  : /a.pdf {/b c.pdf} /d.pdf

    No `break` statements are used; the loop exits by setting `current`
    to an empty string to signal exhaustion.
    """
    paths: list = []
    current = data.strip()

    while current:
        if current.startswith("{"):
            close = current.find("}")
            if close != -1:
                paths.append(current[1:close])
                current = current[close + 1:].strip()
            else:
                # Malformed brace — discard remainder gracefully
                current = ""
        else:
            space = current.find(" ")
            if space != -1:
                paths.append(current[:space])
                current = current[space:].strip()
            else:
                # Last (or only) token — append and signal loop end
                paths.append(current)
                current = ""

    return paths


def _open_in_file_manager(path: Path) -> None:
    """Open *path* in the native file manager (Windows / macOS / Linux)."""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(path))
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass  # Non-fatal: the user can navigate manually


# ============================================================
#  Page-exclusion dialog
# ============================================================

class ExclusionDialog(ctk.CTkToplevel):
    """
    Modal dialog that lets the user specify which pages to REMOVE
    from the merge output for a single PDF.

    The input field accepts a comma-separated list of 1-based page
    numbers and ranges, e.g.  "1, 3-5, 10".
    """

    def __init__(self, master, current_exclusions: str, max_pages: int):
        super().__init__(master)
        self.title("Remove Pages")
        self.geometry("420x240")
        self.resizable(False, False)
        self.max_pages = max_pages
        self.result    = current_exclusions  # preserved if user cancels

        # Instruction label — the word REMOVE is specifically required
        ctk.CTkLabel(
            self,
            text=(
                "Enter page ranges to REMOVE\n"
                "from the final merged output  (e.g.  1, 3-5, 10)"
            ),
            font=("Roboto", 13),
        ).pack(pady=(22, 8))

        self.entry = ctk.CTkEntry(self, width=320)
        self.entry.insert(0, current_exclusions)
        self.entry.pack(pady=6)

        ctk.CTkButton(
            self, text="Confirm", width=120, command=self._confirm,
        ).pack(pady=18)

        self.transient(master)
        self.grab_set()
        # Move focus to the entry so the user can type immediately
        self.after(50, self.entry.focus_set)

    def _confirm(self) -> None:
        self.result = self.entry.get()
        self.destroy()


# ============================================================
#  Shared page-range parser  (used by both exclusion and keep-single)
# ============================================================

def _parse_page_range_string(raw: str) -> set:
    """
    Convert a human-readable page-range string into a set of 0-based indices.

    Accepted format: comma- or space-separated tokens, each either a
    single page number (1-based) or a closed range "a-b" (inclusive).
    Example: "1, 3-5, 10"  ->  {0, 2, 3, 4, 9}

    Malformed tokens are silently ignored.  No `break` is used.
    """
    result: set = set()
    for token in re.split(r"[,\s]+", raw.strip()):
        if "-" in token:
            try:
                a, b = map(int, token.split("-", 1))
                result.update(range(a - 1, b))
            except ValueError:
                pass
        elif token.isdigit():
            result.add(int(token) - 1)
    return result


# ============================================================
#  Keep-single dialog
# ============================================================

class KeepSingleDialog(ctk.CTkToplevel):
    """
    Modal dialog for selecting pages that must remain as single pages
    in the merged output (i.e. they are present but never paired with
    an adjacent page).

    This creates a "pairing barrier": neither the page before nor the page
    after can form a spread across a keep-single page.

    Accepts the same input syntax as ExclusionDialog: comma-separated
    page numbers and ranges (1-based), e.g.  "1, 4, 7-9".
    """

    def __init__(self, master, current_value: str, max_pages: int):
        super().__init__(master)
        self.title("Keep Pages Single")
        self.geometry("460x260")
        self.resizable(False, False)
        self.max_pages = max_pages
        self.result    = current_value

        ctk.CTkLabel(
            self,
            text=(
                "Pages to keep as SINGLE  (never paired with a neighbour)\n\n"
                "These pages stay in the output but always appear alone,\n"
                "acting as a pairing barrier on both sides.\n\n"
                "Format: comma-separated numbers or ranges  (e.g.  1, 4, 7-9)"
            ),
            font=("Roboto", 12),
            justify="left",
        ).pack(padx=22, pady=(18, 8), anchor="w")

        self.entry = ctk.CTkEntry(self, width=340)
        self.entry.insert(0, current_value)
        self.entry.pack(pady=6)

        ctk.CTkButton(
            self, text="Confirm", width=120, command=self._confirm,
        ).pack(pady=14)

        self.transient(master)
        self.grab_set()
        self.after(50, self.entry.focus_set)

    def _confirm(self) -> None:
        self.result = self.entry.get()
        self.destroy()


# ============================================================
#  Merge preview dialog  (paginated, keyboard + scroll navigable)
# ============================================================

class PreviewDialog(ctk.CTkToplevel):
    """
    Shows a paginated thumbnail preview of every spread that will be
    produced for one PDF item.

    Navigation
    ----------
    - Left / Right arrow keys  : previous / next spread
    - Up   / Down  arrow keys  : previous / next spread
    - Mouse scroll wheel       : previous (up) / next (down)
    - Prev / Next buttons      : same as arrows

    Implementation notes
    --------------------
    - The PDF document is opened once and kept open until the dialog
      is destroyed.
    - Spreads are computed up-front in `_build_spread_list`; pages are
      rendered on-demand in `_render_spread` to keep memory usage low.
    - No `break` statements are used.
    """

    # Render scale: 0.20 keeps thumbnails crisp but not huge
    _SCALE = 0.20

    def __init__(self, master, item_data: dict, manga_mode: bool):
        super().__init__(master)
        self.title("Merge Preview")
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()

        # ---- internal state ----
        self._doc:         "fitz.Document | None" = None
        self._manga_mode:  bool                   = manga_mode
        self._spreads:     list                   = []  # list of (a, b|None)
        self._current:     int                    = 0
        self._image_ref                           = None  # GC guard

        # ---- build content ----
        self._build_spread_list(item_data)
        self._build_ui()

        # ---- keyboard bindings ----
        self.bind("<Left>",       lambda _e: self._navigate(-1))
        self.bind("<Right>",      lambda _e: self._navigate(1))
        self.bind("<Up>",         lambda _e: self._navigate(-1))
        self.bind("<Down>",       lambda _e: self._navigate(1))
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Button-4>",   self._on_wheel)   # Linux scroll up
        self.bind("<Button-5>",   self._on_wheel)   # Linux scroll down

        # Show the first spread (or the empty-state message)
        if self._spreads:
            self._show_spread(0)

    # ------------------------------------------------------------------
    # Spread list construction
    # ------------------------------------------------------------------

    def _build_spread_list(self, data: dict) -> None:
        """
        Replicate the page-pipeline from logic._process_single_file so
        the preview exactly mirrors what the output PDF will contain.

        Populates self._spreads with tuples:
          (a, b)    — two-page spread  (b is None for a single page)

        keep_single pages are present but act as pairing barriers:
        they are never paired with the page before or after them.
        """
        cover_alone:  bool = data.get("cover_alone", False)
        start:        int  = data["start"]
        end:          int  = data["end"]
        excluded:     set  = data["exclude"]
        keep_single:  set  = data.get("keep_single", set())

        try:
            self._doc  = fitz.open(data["path"])
            n          = len(self._doc)
            range_start = start

            # 1. Cover page
            if cover_alone and start == 0 and n > 0 and 0 not in excluded:
                self._spreads.append((0, None))
                range_start = 1

            # 2. Pre-range singles
            pre_first = 1 if (cover_alone and start == 0) else 0
            for p in range(pre_first, start):
                if p not in excluded and p < n:
                    self._spreads.append((p, None))

            # 3. Paired range (same barrier logic as logic._process_single_file)
            valid = [
                p for p in range(range_start, end)
                if p not in excluded and p < n
            ]
            pair_idx = 0
            while pair_idx < len(valid):
                left  = valid[pair_idx]
                left_is_single  = left in keep_single

                has_right       = pair_idx + 1 < len(valid)
                right           = valid[pair_idx + 1] if has_right else -1
                right_is_single = has_right and (right in keep_single)

                can_pair = has_right and not left_is_single and not right_is_single

                if can_pair:
                    self._spreads.append((left, right))
                    pair_idx += 2
                else:
                    self._spreads.append((left, None))
                    pair_idx += 1

            # 4. Post-range singles
            for p in range(end, n):
                if p not in excluded:
                    self._spreads.append((p, None))

        except Exception as exc:
            self._build_error = str(exc)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Create the dialog layout: image area, info label, nav bar."""

        # -- Error state ------------------------------------------------
        if hasattr(self, "_build_error"):
            ctk.CTkLabel(
                self,
                text=f"Cannot generate preview:\n{self._build_error}",
                font=("Roboto", 12),
                text_color="#E74C3C",
            ).pack(padx=20, pady=30)
            self.geometry("440x130")
            return

        if not self._spreads:
            ctk.CTkLabel(
                self,
                text="No pages in the selected range.",
                font=("Roboto", 13),
            ).pack(padx=20, pady=30)
            self.geometry("380x100")
            return

        # -- Image display (updated on navigation) ----------------------
        self._image_label = ctk.CTkLabel(self, text="Loading preview…")
        self._image_label.pack(padx=10, pady=(10, 4))

        # -- Spread info label ------------------------------------------
        self._info_label = ctk.CTkLabel(
            self, text="",
            font=("Roboto", 11), text_color="#95A5A6",
        )
        self._info_label.pack(pady=(0, 4))

        # -- Navigation bar ---------------------------------------------
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(pady=(0, 12))

        self._btn_prev = ctk.CTkButton(
            nav, text="◀  Prev", width=96, height=30,
            fg_color="#2C3E50", hover_color="#1A252F",
            command=lambda: self._navigate(-1),
        )
        self._btn_prev.pack(side="left", padx=6)

        # Page counter label (fixed width prevents layout jitter)
        self._counter_label = ctk.CTkLabel(
            nav, text="",
            font=("Roboto", 12, "bold"), width=90,
        )
        self._counter_label.pack(side="left", padx=4)

        self._btn_next = ctk.CTkButton(
            nav, text="Next  ▶", width=96, height=30,
            fg_color="#2C3E50", hover_color="#1A252F",
            command=lambda: self._navigate(1),
        )
        self._btn_next.pack(side="left", padx=6)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate(self, delta: int) -> None:
        """Move `delta` spreads relative to the current position."""
        if not self._spreads:
            return
        new_idx = max(0, min(self._current + delta, len(self._spreads) - 1))
        if new_idx != self._current:
            self._show_spread(new_idx)

    def _on_wheel(self, event) -> None:
        """Translate scroll-wheel events into spread navigation."""
        if event.delta != 0:
            direction = 1 if event.delta < 0 else -1   # scroll down = next
        else:
            direction = 1 if event.num == 5 else -1    # Button-5 = scroll down
        self._navigate(direction)

    # ------------------------------------------------------------------
    # Spread rendering
    # ------------------------------------------------------------------

    def _show_spread(self, idx: int) -> None:
        """
        Render spread at position *idx* and update the image label,
        info text, counter, and window geometry.
        """
        self._current  = idx
        spread         = self._spreads[idx]
        left_page_idx, right_page_idx = spread   # right may be None

        mat = fitz.Matrix(self._SCALE, self._SCALE)

        def _page_to_pil(page_idx: int) -> Image.Image:
            pix = self._doc[page_idx].get_pixmap(matrix=mat)
            return Image.open(io.BytesIO(pix.tobytes("png")))

        if right_page_idx is not None:
            # ---- Two-page spread (respect Eastern / Western order) ----
            if self._manga_mode:
                # Eastern: right-to-left — the higher page index appears
                # on the visual LEFT of the spread
                pil_left  = _page_to_pil(right_page_idx)
                pil_right = _page_to_pil(left_page_idx)
                label_left_num  = right_page_idx + 1
                label_right_num = left_page_idx  + 1
                mode_str = "Eastern  (right-to-left)"
            else:
                pil_left  = _page_to_pil(left_page_idx)
                pil_right = _page_to_pil(right_page_idx)
                label_left_num  = left_page_idx  + 1
                label_right_num = right_page_idx + 1
                mode_str = "Western  (left-to-right)"

            # Combine both thumbnails into one PIL image side-by-side
            combined_w = pil_left.width + pil_right.width + 4  # 4px separator
            combined_h = max(pil_left.height, pil_right.height)
            canvas     = Image.new("RGB", (combined_w, combined_h), (59, 142, 208))
            canvas.paste(pil_left,  (0, 0))
            canvas.paste(pil_right, (pil_left.width + 4, 0))

            ctk_img = ctk.CTkImage(
                light_image=canvas, dark_image=canvas,
                size=(combined_w, combined_h),
            )
            info = (
                f"Mode: {mode_str}    "
                f"Page {label_left_num}  |  Page {label_right_num}"
            )
            geom_w = combined_w + 40
            geom_h = combined_h + 110

        else:
            # ---- Single page ------------------------------------------
            pil_single = _page_to_pil(left_page_idx)
            ctk_img    = ctk.CTkImage(
                light_image=pil_single, dark_image=pil_single,
                size=(pil_single.width, pil_single.height),
            )
            info    = f"Single page  (page {left_page_idx + 1})"
            geom_w  = pil_single.width + 40
            geom_h  = pil_single.height + 110

        # Keep a reference so the garbage collector does not drop the image
        self._image_ref = ctk_img

        # Update the image, info text, counter, and nav buttons
        self._image_label.configure(image=ctk_img, text="")
        self._info_label.configure(text=info)
        self._counter_label.configure(
            text=f"{idx + 1} / {len(self._spreads)}"
        )
        self._btn_prev.configure(state="normal" if idx > 0 else "disabled")
        self._btn_next.configure(
            state="normal" if idx < len(self._spreads) - 1 else "disabled"
        )

        # Clamp geometry to a reasonable maximum so large PDFs don't overflow
        max_w, max_h = 1200, 900
        self.geometry(f"{min(geom_w, max_w)}x{min(geom_h, max_h)}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def destroy(self) -> None:
        """Close the fitz document before destroying the window."""
        if self._doc is not None:
            try:
                self._doc.close()
            except Exception:
                pass
            self._doc = None
        super().destroy()


# ============================================================
#  Error log dialog
# ============================================================

class ErrorLogDialog(ctk.CTkToplevel):
    """
    Scrollable dialog that lists every file that failed during the merge
    batch, along with its exception message.
    """

    def __init__(self, master, errors: list):
        super().__init__(master)
        self.title("Error Log")
        self.geometry("540x380")
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(
            self,
            text=f"  {len(errors)} file(s) could not be processed",
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
                font=("Roboto", 12, "bold"),
                text_color="#E74C3C",
            ).pack(anchor="w", padx=10, pady=(6, 0))
            ctk.CTkLabel(
                card, text=msg,
                font=("Roboto", 11),
                text_color="#95A5A6",
                wraplength=470, justify="left",
            ).pack(anchor="w", padx=10, pady=(0, 6))

        ctk.CTkButton(self, text="Close", command=self.destroy).pack(pady=10)


# ============================================================
#  PDF list item
# ============================================================

class PDFItem(ctk.CTkFrame):
    """
    A single row in the document list that represents one source PDF.

    Public interface
    ----------------
    get_data()      -> dict   : data dict consumed by logic.elabora_documento
    get_state()     -> dict   : full snapshot for undo/redo
    restore_state() -> None   : restore from a snapshot
    """

    def __init__(self, master, file_path: str, app: "PDFPageMergerGUI"):
        super().__init__(master)
        self.file_path       = file_path
        self.app             = app
        self.exclusions      = ""    # pages to fully REMOVE from output
        self.keep_single_str = ""    # pages to keep but never pair
        self._drag_y_anchor: int = 0   # y_root captured at drag start

        # Open briefly to count pages, then close
        doc = fitz.open(file_path)
        self.max_pages = len(doc)
        doc.close()

        is_single  = self.max_pages <= 1
        slider_to  = 1.1          if is_single else self.max_pages
        step_count = 1            if is_single else self.max_pages - 1

        # ----------------------------------------------------------------
        # Header row
        # ----------------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(6, 0))

        # Drag handle — mouse bindings produce reorder via _drag_* methods
        drag_handle = ctk.CTkLabel(
            header, text=":::",
            font=("Roboto", 14, "bold"),
            text_color="#5D6D7E",
            cursor="fleur",
        )
        drag_handle.pack(side="left", padx=(0, 6))
        drag_handle.bind("<ButtonPress-1>",   self._drag_start)
        drag_handle.bind("<B1-Motion>",       self._drag_motion)
        drag_handle.bind("<ButtonRelease-1>", self._drag_end)

        # File name label
        ctk.CTkLabel(
            header,
            text=os.path.basename(file_path),
            font=("Roboto", 12, "bold"),
            text_color="#2ecc71",
        ).pack(side="left")

        # Page count badge
        ctk.CTkLabel(
            header,
            text=f"  •  {self.max_pages} pages",
            font=("Roboto", 11),
            text_color="#95A5A6",
        ).pack(side="left")

        # Right-side action buttons (packed right-to-left)
        ctk.CTkButton(
            header, text="X", width=28, height=22,
            fg_color="#C0392B", hover_color="#A93226",
            command=lambda: app.remove_pdf(self),
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            header, text="Down", width=48, height=22,
            fg_color="#34495E", hover_color="#2C3E50",
            command=lambda: app.move_down(self),
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            header, text="Up", width=36, height=22,
            fg_color="#34495E", hover_color="#2C3E50",
            command=lambda: app.move_up(self),
        ).pack(side="right", padx=2)

        # Page-exclusion button — turns orange when exclusions are active
        self.btn_exclude = ctk.CTkButton(
            header, text="Remove Pages", width=96, height=22,
            fg_color="#5D6D7E", hover_color="#4A5568",
            command=self._open_exclusion_dialog,
        )
        self.btn_exclude.pack(side="right", padx=2)

        # Keep-single button — turns teal when active
        self.btn_keep_single = ctk.CTkButton(
            header, text="Keep Single", width=88, height=22,
            fg_color="#5D6D7E", hover_color="#4A5568",
            command=self._open_keep_single_dialog,
        )
        self.btn_keep_single.pack(side="right", padx=2)

        # Preview button
        ctk.CTkButton(
            header, text="Preview", width=64, height=22,
            fg_color="#1A5276", hover_color="#154360",
            command=lambda: app.show_preview(self),
        ).pack(side="right", padx=2)

        # ----------------------------------------------------------------
        # Cover-alone option
        # ----------------------------------------------------------------
        self.cover_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self,
            text="Keep cover page alone  (page 1 is never paired)",
            variable=self.cover_var,
            font=("Roboto", 11),
        ).pack(anchor="w", padx=22, pady=(6, 0))

        # ----------------------------------------------------------------
        # Start slider
        # ----------------------------------------------------------------
        self.lbl_start = ctk.CTkLabel(
            self, text="Start: 1", font=("Roboto", 13, "bold"),
        )
        self.lbl_start.pack(padx=20, anchor="w", pady=(4, 0))
        self.slider_start = ctk.CTkSlider(
            self, from_=1, to=slider_to,
            number_of_steps=step_count, height=18,
            command=self._update_labels,
        )
        self.slider_start.set(1)
        self.slider_start.pack(fill="x", padx=20)

        # ----------------------------------------------------------------
        # End slider
        # ----------------------------------------------------------------
        self.lbl_end = ctk.CTkLabel(
            self, text=f"End: {self.max_pages}", font=("Roboto", 13, "bold"),
        )
        self.lbl_end.pack(padx=20, anchor="w", pady=(4, 0))
        self.slider_end = ctk.CTkSlider(
            self, from_=1, to=slider_to,
            number_of_steps=step_count, height=18,
            command=self._update_labels,
        )
        self.slider_end.set(self.max_pages)
        self.slider_end.pack(fill="x", padx=20, pady=(0, 10))

        # Disable sliders for single-page PDFs (nothing to range)
        if is_single:
            self.slider_start.configure(state="disabled")
            self.slider_end.configure(state="disabled")

    # ----------------------------------------------------------------
    # Drag-to-reorder (internal list DnD)
    # ----------------------------------------------------------------

    def _drag_start(self, event) -> None:
        self._drag_y_anchor  = event.y_root
        self.app._drag_item  = self

    def _drag_motion(self, event) -> None:
        """
        On motion, compute vertical displacement and swap with neighbour
        when the cursor crosses the midpoint of this widget's height.
        No `break` is used; early exit is handled by an outer condition.
        """
        if self.app._drag_item is not self:
            return

        dy        = event.y_root - self._drag_y_anchor
        threshold = max(self.winfo_height() * 0.45, 30)
        idx       = self.app.items.index(self)

        if dy < -threshold and idx > 0:
            self.app._drag_snapshot()
            self.app._swap_items(idx, idx - 1)
            self._drag_y_anchor = event.y_root
        elif dy > threshold and idx < len(self.app.items) - 1:
            self.app._drag_snapshot()
            self.app._swap_items(idx, idx + 1)
            self._drag_y_anchor = event.y_root

    def _drag_end(self, event) -> None:
        self.app._drag_item    = None
        self.app._drag_snapped = False

    # ----------------------------------------------------------------
    # Page exclusion
    # ----------------------------------------------------------------

    def _open_exclusion_dialog(self) -> None:
        dialog = ExclusionDialog(
            self.winfo_toplevel(), self.exclusions, self.max_pages
        )
        self.master.wait_window(dialog)
        self.exclusions = dialog.result
        # Visual feedback: orange when exclusions are active
        self.btn_exclude.configure(
            fg_color="#F39C12" if self.exclusions.strip() else "#5D6D7E"
        )

    def _open_keep_single_dialog(self) -> None:
        """Open the dialog for selecting pages to keep single (not paired)."""
        dialog = KeepSingleDialog(
            self.winfo_toplevel(), self.keep_single_str, self.max_pages
        )
        self.master.wait_window(dialog)
        self.keep_single_str = dialog.result
        # Visual feedback: teal when keep-single pages are active
        self.btn_keep_single.configure(
            fg_color="#117A65" if self.keep_single_str.strip() else "#5D6D7E"
        )

    def _parse_exclusions(self) -> set:
        """
        Convert the exclusion string (e.g. "1, 3-5, 10") into a set of
        0-based page indices.  No `break` is used.
        """
        return _parse_page_range_string(self.exclusions)

    def _parse_keep_single(self) -> set:
        """
        Convert the keep-single string into a set of 0-based page indices.
        Reuses the same parser as exclusions.
        """
        return _parse_page_range_string(self.keep_single_str)

    # ----------------------------------------------------------------
    # Slider label synchronisation
    # ----------------------------------------------------------------

    def _update_labels(self, _=None) -> None:
        s = int(self.slider_start.get())
        e = int(self.slider_end.get())
        # Prevent start > end
        if s > e:
            self.slider_start.set(e)
            s = e
        self.lbl_start.configure(text=f"Start: {s}")
        self.lbl_end.configure(text=f"End: {e}")

    # ----------------------------------------------------------------
    # Data / state API
    # ----------------------------------------------------------------

    def get_data(self) -> dict:
        """Return the task dict consumed by logic.elabora_documento."""
        return {
            "path":         self.file_path,
            "start":        int(self.slider_start.get()) - 1,
            "end":          int(self.slider_end.get()),
            "exclude":      self._parse_exclusions(),
            "keep_single":  self._parse_keep_single(),
            "cover_alone":  self.cover_var.get(),
        }

    def get_state(self) -> dict:
        """Return a full snapshot suitable for undo/redo storage."""
        return {
            "path":            self.file_path,
            "slider_s":        self.slider_start.get(),
            "slider_e":        self.slider_end.get(),
            "exclusions":      self.exclusions,
            "keep_single_str": self.keep_single_str,
            "cover_alone":     self.cover_var.get(),
        }

    def restore_state(self, state: dict) -> None:
        """Restore this item's state from a previously saved snapshot."""
        self.exclusions      = state["exclusions"]
        self.keep_single_str = state.get("keep_single_str", "")
        self.slider_start.set(state["slider_s"])
        self.slider_end.set(state["slider_e"])
        self.cover_var.set(state["cover_alone"])
        self._update_labels()
        self.btn_exclude.configure(
            fg_color="#F39C12" if self.exclusions.strip() else "#5D6D7E"
        )
        self.btn_keep_single.configure(
            fg_color="#117A65" if self.keep_single_str.strip() else "#5D6D7E"
        )


# ============================================================
#  Main application window
# ============================================================

class PDFPageMergerGUI(ctk.CTk, TkinterDnD.DnDWrapper):
    """
    Top-level window for PDF Page Merger.

    Keyboard shortcuts
    ------------------
    Ctrl+Z          : Undo last list change
    Ctrl+Y          : Redo
    Ctrl+Shift+Z    : Redo (alternative)
    """

    _MAX_UNDO = 25   # maximum number of undo snapshots retained

    def __init__(self):
        super().__init__()
        self._init_tkdnd()

        self.title("PDF Page Merger")
        self.geometry("760x730")
        self.minsize(580, 520)

        # ---- application state ----
        self.items:          list = []
        self._undo_stack:    list = []
        self._redo_stack:    list = []
        self._drag_item           = None
        self._drag_snapped:  bool = False   # True after first swap in a drag
        self._is_restoring:  bool = False   # guard against recursive snapshots

        # Output folder (defaults to Documents/pdf-page-merger)
        default_out = get_documents_path() / "pdf-page-merger"
        self.output_dir_var = ctk.StringVar(value=str(default_out))

        # Current appearance mode
        self._theme_mode: str = ctk.get_appearance_mode().lower()

        self._build_ui()
        self._bind_mouse_wheel(self)

        # Global keyboard shortcuts for undo / redo
        self.bind("<Control-z>", lambda _e: self._undo())
        self.bind("<Control-y>", lambda _e: self._redo())
        self.bind("<Control-Z>", lambda _e: self._redo())  # Ctrl+Shift+Z

    # ============================================================
    #  tkdnd initialisation
    # ============================================================

    def _init_tkdnd(self) -> None:
        """Load the native tkdnd library for the current platform."""
        try:
            import tkinterdnd2
            subdir = _get_tkdnd_subdir()
            if subdir is None:
                return
            lib_path = os.path.join(
                os.path.dirname(tkinterdnd2.__file__), "tkdnd", subdir
            )
            self.tk.call("lappend", "auto_path", lib_path)
            self.tk.call("package", "require", "tkdnd")
        except Exception:
            pass  # DnD is optional; manual file selection still works

    # ============================================================
    #  Mouse-wheel binding (recursive, applied to all child widgets)
    # ============================================================

    def _bind_mouse_wheel(self, widget) -> None:
        try:
            widget.bind("<MouseWheel>", self._on_mouse_wheel)
            widget.bind("<Button-4>",   self._on_mouse_wheel)
            widget.bind("<Button-5>",   self._on_mouse_wheel)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_mouse_wheel(child)

    def _on_mouse_wheel(self, event) -> None:
        if not self.items:
            return
        direction = (-1 if event.delta > 0 else 1) if event.delta != 0 \
                    else (-1 if event.num == 4 else 1)
        try:
            self.scroll_frame._parent_canvas.yview_scroll(direction, "units")
        except Exception:
            pass

    # ============================================================
    #  UI construction
    # ============================================================

    def _build_ui(self) -> None:
        # ---- Top bar ------------------------------------------------
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=18, pady=(12, 0))

        ctk.CTkLabel(
            top_bar, text="PDF Page Merger",
            font=("Roboto", 22, "bold"),
        ).pack(side="left")

        # Theme toggle — solid background, no emoji, text-only label
        theme_label = "Switch to Light" if self._theme_mode == "dark" \
                      else "Switch to Dark"
        self.btn_theme = ctk.CTkButton(
            top_bar,
            text=theme_label,
            width=120, height=28,
            fg_color="#546E7A",          # slate-grey: visible on both themes
            hover_color="#37474F",
            text_color="white",
            command=self._toggle_theme,
        )
        self.btn_theme.pack(side="right", padx=(4, 0))

        # Redo button
        self.btn_redo = ctk.CTkButton(
            top_bar, text="Redo", width=72, height=28,
            fg_color="#1A5276", hover_color="#154360",
            state="disabled", command=self._redo,
        )
        self.btn_redo.pack(side="right", padx=2)

        # Undo button
        self.btn_undo = ctk.CTkButton(
            top_bar, text="Undo", width=72, height=28,
            fg_color="#1A5276", hover_color="#154360",
            state="disabled", command=self._undo,
        )
        self.btn_undo.pack(side="right", padx=2)

        # ---- Reading-direction toggle --------------------------------
        self.style_var = ctk.StringVar(value="Eastern")
        ctk.CTkSegmentedButton(
            self,
            values=["Eastern", "Western"],
            variable=self.style_var,
        ).pack(pady=8)

        # ---- Compression option row ---------------------------------
        opt_row = ctk.CTkFrame(self, fg_color="transparent")
        opt_row.pack(fill="x", padx=18, pady=(0, 4))

        ctk.CTkLabel(
            opt_row, text="Output compression:",
            font=("Roboto", 12),
        ).pack(side="left")
        self.compress_var = ctk.StringVar(value="Medium")
        ctk.CTkComboBox(
            opt_row,
            values=list(COMPRESS_PRESETS.keys()),
            variable=self.compress_var,
            width=120,
        ).pack(side="left", padx=(8, 0))

        # ---- Output-folder row --------------------------------------
        out_row = ctk.CTkFrame(self, fg_color="transparent")
        out_row.pack(fill="x", padx=18, pady=(0, 6))

        ctk.CTkLabel(
            out_row, text="Output folder:", font=("Roboto", 12),
        ).pack(side="left")
        ctk.CTkLabel(
            out_row,
            textvariable=self.output_dir_var,
            font=("Roboto", 11), text_color="#95A5A6", anchor="w",
        ).pack(side="left", padx=6, fill="x", expand=True)
        ctk.CTkButton(
            out_row, text="Change", width=72, height=26,
            fg_color="#1b5e20", hover_color="#145A32",
            command=self._select_output_folder,
        ).pack(side="right")

        # ---- Drop zone ----------------------------------------------
        self.drop_frame = ctk.CTkFrame(
            self, height=68, border_width=2, border_color="#3b8ed0",
        )
        self.drop_frame.pack(pady=6, padx=18, fill="x")
        self.drop_frame.pack_propagate(False)
        ctk.CTkLabel(
            self.drop_frame,
            text="Drop PDF files here  •  Multiple files supported",
        ).pack(expand=True)
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)

        ctk.CTkButton(
            self, text="Browse Files", command=self._browse_files,
            fg_color="#1b5e20", hover_color="#145A32", height=32,
        ).pack(pady=4)

        # ---- Scrollable document list (added on first file) ---------
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, label_text="Document List",
        )

        # ---- Progress container (hidden until merge starts) ---------
        self.progress_container = ctk.CTkFrame(self, fg_color="transparent")

        self.lbl_current_file = ctk.CTkLabel(
            self.progress_container, text="",
            font=("Roboto", 11), text_color="#95A5A6",
        )
        self.lbl_current_file.pack(pady=(6, 0))

        self.progress_file = ctk.CTkProgressBar(self.progress_container)
        self.progress_file.set(0)
        self.progress_file.pack(fill="x", padx=50, pady=2)

        self.lbl_overall = ctk.CTkLabel(
            self.progress_container, text="",
            font=("Roboto", 11), text_color="#95A5A6",
        )
        self.lbl_overall.pack()

        self.progress_overall = ctk.CTkProgressBar(self.progress_container)
        self.progress_overall.set(0)
        self.progress_overall.pack(fill="x", padx=50, pady=(2, 8))

        # ---- Merge button (always anchored to the bottom) -----------
        self.btn_merge = ctk.CTkButton(
            self, text="MERGE PDF", command=self._run_merge,
            state="disabled", font=("Roboto", 14, "bold"), height=42,
        )
        self.btn_merge.pack(pady=12, side="bottom")

    # ============================================================
    #  File management
    # ============================================================

    def _browse_files(self) -> None:
        paths = ctk.filedialog.askopenfilenames(
            filetypes=[("PDF Files", "*.pdf")]
        )
        for p in paths:
            self._add_pdf(p)

    def _on_drop(self, event) -> None:
        for p in _parse_drop_paths(event.data):
            if p.lower().endswith(".pdf"):
                self._add_pdf(p)

    def _add_pdf(self, path: str) -> None:
        """
        Add a PDF to the list after checking for duplicates.
        A snapshot is taken before the change to support undo.
        """
        # Duplicate guard
        if any(item.file_path == path for item in self.items):
            CTkMessagebox(
                title="Already in list",
                message=f"This file is already loaded:\n{os.path.basename(path)}",
                icon="warning",
            )
            return

        self._snapshot()   # save state for undo

        # Show the scroll frame on the first file
        if not self.items:
            self.scroll_frame.pack(
                pady=5, padx=18, fill="both", expand=True,
                before=self.btn_merge,
            )

        item = PDFItem(self.scroll_frame, path, self)
        item.pack(fill="x", pady=5, padx=5)
        self.items.append(item)
        self._bind_mouse_wheel(item)
        self.btn_merge.configure(state="normal")

    def remove_pdf(self, item: PDFItem) -> None:
        self._snapshot()
        item.destroy()
        self.items.remove(item)
        if not self.items:
            self.scroll_frame.pack_forget()
            self.btn_merge.configure(state="disabled")

    def move_up(self, item: PDFItem) -> None:
        idx = self.items.index(item)
        if idx > 0:
            self._snapshot()
            self.items[idx], self.items[idx - 1] = self.items[idx - 1], self.items[idx]
            self._refresh_list()

    def move_down(self, item: PDFItem) -> None:
        idx = self.items.index(item)
        if idx < len(self.items) - 1:
            self._snapshot()
            self.items[idx], self.items[idx + 1] = self.items[idx + 1], self.items[idx]
            self._refresh_list()

    def _refresh_list(self) -> None:
        """Re-pack all items in their current order."""
        for item in self.items:
            item.pack_forget()
            item.pack(fill="x", pady=5, padx=5)

    # ============================================================
    #  Internal drag-to-reorder helpers
    # ============================================================

    def _drag_snapshot(self) -> None:
        """Take a snapshot only on the first swap of the current drag gesture."""
        if not self._drag_snapped:
            self._snapshot()
            self._drag_snapped = True

    def _swap_items(self, a: int, b: int) -> None:
        self.items[a], self.items[b] = self.items[b], self.items[a]
        self._refresh_list()

    # ============================================================
    #  Undo / Redo
    # ============================================================

    def _snapshot(self) -> None:
        """
        Save the current list state onto the undo stack.
        Called before every mutating operation.
        Does nothing while a restore is in progress (guard flag).
        """
        if self._is_restoring:
            return
        state = [item.get_state() for item in self.items]
        self._undo_stack.append(state)
        if len(self._undo_stack) > self._MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_undo_buttons()

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append([item.get_state() for item in self.items])
        self._restore_state(self._undo_stack.pop())
        self._update_undo_buttons()

    def _redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append([item.get_state() for item in self.items])
        self._restore_state(self._redo_stack.pop())
        self._update_undo_buttons()

    def _restore_state(self, state: list) -> None:
        """
        Rebuild the item list from a snapshot.
        The `_is_restoring` guard prevents snapshot() from being triggered
        by the item additions that happen during the restore.
        """
        self._is_restoring = True
        try:
            for item in self.items[:]:
                item.destroy()
            self.items.clear()

            for saved in state:
                item = PDFItem(self.scroll_frame, saved["path"], self)
                item.pack(fill="x", pady=5, padx=5)
                item.restore_state(saved)
                self.items.append(item)
                self._bind_mouse_wheel(item)

            if self.items:
                # Re-show the scroll frame if it was hidden
                try:
                    self.scroll_frame.pack_info()
                except Exception:
                    self.scroll_frame.pack(
                        pady=5, padx=18, fill="both", expand=True,
                        before=self.btn_merge,
                    )
                self.btn_merge.configure(state="normal")
            else:
                self.scroll_frame.pack_forget()
                self.btn_merge.configure(state="disabled")
        finally:
            self._is_restoring = False

    def _update_undo_buttons(self) -> None:
        self.btn_undo.configure(state="normal" if self._undo_stack else "disabled")
        self.btn_redo.configure(state="normal" if self._redo_stack else "disabled")

    # ============================================================
    #  Preview
    # ============================================================

    def show_preview(self, item: PDFItem) -> None:
        """Open a PreviewDialog for the given PDF item."""
        PreviewDialog(
            self,
            item.get_data(),
            manga_mode=self.style_var.get() == "Eastern",
        )

    # ============================================================
    #  Theme toggle
    # ============================================================

    def _toggle_theme(self) -> None:
        """Switch between dark and light appearance modes."""
        self._theme_mode = "light" if self._theme_mode == "dark" else "dark"
        ctk.set_appearance_mode(self._theme_mode)
        self.btn_theme.configure(
            text=(
                "Switch to Light"
                if self._theme_mode == "dark"
                else "Switch to Dark"
            )
        )

    # ============================================================
    #  Output folder selection
    # ============================================================

    def _select_output_folder(self) -> None:
        chosen = ctk.filedialog.askdirectory(
            title="Select output folder",
            initialdir=self.output_dir_var.get(),
        )
        if chosen:
            self.output_dir_var.set(chosen)

    # ============================================================
    #  Progress callbacks (called from the merge thread via idletasks)
    # ============================================================

    def _cb_overall(self, value: float) -> None:
        self.progress_overall.set(value)
        total = len(self.items)
        done  = round(value * total)
        self.lbl_overall.configure(text=f"Overall: {done} / {total} files")
        self.update_idletasks()

    def _cb_file(self, filename: str, value: float) -> None:
        self.lbl_current_file.configure(text=f"  {filename}")
        self.progress_file.set(value)
        self.update_idletasks()

    # ============================================================
    #  Merge execution
    # ============================================================

    def _run_merge(self) -> None:
        """Collect tasks, show progress UI, run the merge, show results."""
        # Show progress area
        self.progress_container.pack(
            fill="x", padx=18, pady=4, before=self.btn_merge,
        )
        self.progress_overall.set(0)
        self.progress_file.set(0)
        self.lbl_current_file.configure(text="Starting…")
        self.lbl_overall.configure(text="")
        self.btn_merge.configure(state="disabled")
        self.update()

        tasks   = [item.get_data() for item in self.items]
        outputs: list = []
        errors:  list = []

        try:
            outputs, errors = elabora_documento(
                tasks,
                manga_mode       = self.style_var.get() == "Eastern",
                output_dir       = Path(self.output_dir_var.get()),
                compress_preset  = self.compress_var.get(),
                callback_totale  = self._cb_overall,
                callback_file    = self._cb_file,
            )
        except Exception as exc:
            CTkMessagebox(
                title="Critical error", message=str(exc), icon="cancel",
            )
        else:
            self._show_results(outputs, errors)
        finally:
            self.progress_container.pack_forget()
            self.btn_merge.configure(state="normal")

    def _show_results(self, outputs: list, errors: list) -> None:
        """Display the appropriate result dialog based on success/error counts."""
        output_dir = Path(self.output_dir_var.get())
        n_ok  = len(outputs)
        n_err = len(errors)

        if n_err == 0:
            # All files succeeded
            dlg = CTkMessagebox(
                title="Complete",
                message=f"{n_ok} file(s) merged successfully!\n{output_dir}",
                icon="check",
                option_1="Open Folder",
                option_2="OK",
            )
            if dlg.get() == "Open Folder":
                _open_in_file_manager(output_dir)

        elif n_ok == 0:
            # All files failed
            CTkMessagebox(
                title="Error",
                message=(
                    f"All {n_err} file(s) encountered errors.\n"
                    "Check the error log for details."
                ),
                icon="cancel",
            )
            ErrorLogDialog(self, errors)

        else:
            # Mixed result
            dlg = CTkMessagebox(
                title="Completed with warnings",
                message=(
                    f"{n_ok} file(s) merged successfully\n"
                    f"{n_err} file(s) had errors\n"
                    f"{output_dir}"
                ),
                icon="warning",
                option_1="Open Folder",
                option_2="View Errors",
                option_3="OK",
            )
            choice = dlg.get()
            if choice == "Open Folder":
                _open_in_file_manager(output_dir)
            elif choice == "View Errors":
                ErrorLogDialog(self, errors)
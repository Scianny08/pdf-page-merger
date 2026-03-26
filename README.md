# 📚 PDF Page Merger

**PDF Page Merger** is a vibe coded desktop application built in Python for manga and comic enthusiasts.
It merges single pages into side-by-side spreads without any loss of content,
optimising the reading experience on tablets and wide screens.

---

## ✨ Features

**Dual Mode**
Choose the reading direction before starting the merge:
- **Eastern** — Right → Left, ideal for manga
- **Western** — Left → Right, for comics and documents

**Multi-File Management**
Load multiple PDFs at once. Reorder them with the `Up` / `Down` buttons or by dragging the `:::` handle on the left of each row.

**Selective Merging**
Use the sliders on each file to define the exact page range to merge.
Pages outside the range (covers, credits) and odd pages out are kept as singles — no content is ever lost.

**Page Exclusion**
The `Remove Pages` button opens a dialog to completely remove specific pages or ranges from the output (e.g. `1, 3-5, 10`). The button turns orange when exclusions are active.

**Keep Single**
The `Keep Single` button lets you mark pages that must stay as singles in the output without being removed: they act as a pairing barrier on both sides. The button turns teal when active.

**Merge Preview**
The `Preview` button on each file opens a window showing a thumbnail of every spread that will be produced, navigable with the arrow keys or the mouse wheel.

**Output Compression**
Select the compression level of the output PDF from three presets: `None`, `Medium`, `High`.

**Custom Output Folder**
The default destination is `Documents/pdf-page-merger/`. You can change it with the `Change` button. Output files are saved with the suffix `- EASTERN` or `- WESTERN`.

**Undo / Redo**
All changes to the file list are reversible with `Ctrl+Z` (Undo) and `Ctrl+Y` / `Ctrl+Shift+Z` (Redo), up to 25 steps.

**Drag & Drop**
Drag PDF files directly into the drop area. Supported on Windows, macOS, and Linux.

**Duplicate Detection**
Files already present in the list are not added a second time.

**Dual Progress Bars**
During the merge, two progress bars are shown: one for the current file, one for the overall batch progress.

**Error Log**
If any files fail, a dedicated dialog lists them along with their error message. The merge of the remaining files continues normally.

**Light / Dark Theme**
The `Switch to Light / Switch to Dark` button in the top-right corner toggles the interface theme.

---

## 🖥️ Compatibility

| Operating System | Supported Architectures |
|---|---|
| Windows | x86, x64 |
| macOS | Intel (x86_64), Apple Silicon (arm64) |
| Linux | x86, x86_64, ARM64 |

---

## 🚀 Installation

### Prerequisites

- **Python 3.10** or higher

### 1. Clone or download the project

```bash
git clone https://github.com/your-username/pdf-page-merger.git
cd pdf-page-merger
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate it

```bash
# Windows
.\.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

**Dependencies (`requirements.txt`):**

| Library | Description |
|---|---|
| `customtkinter` | Modern graphical interface |
| `pymupdf` | PDF processing engine |
| `tkinterdnd2` | Native Drag & Drop support |
| `ctkmessagebox` | Dialog windows |
| `Pillow` | Image handling and app icon |

---

## 🛠️ Usage

### Launch

```bash
python main.py
```

### Workflow

1. **Load** PDFs by dragging them into the drop area or using the **Browse Files** button
2. **Reorder** files with `Up` / `Down` or by dragging the `:::` handle
3. **Configure** each file:
   - Use the **sliders** to define the page range to merge
   - Use **`Remove Pages`** to exclude specific pages or ranges (e.g. `1, 3-5, 10`)
   - Use **`Keep Single`** for pages that must stay isolated without being removed
   - Use **`Preview`** to check the result before merging
4. **Choose** the **Eastern** or **Western** mode
5. **Choose** the output **compression** level
6. **Start** with the **MERGE PDF** button

Output files are saved in the selected output folder (default: `Documents/pdf-page-merger/`).
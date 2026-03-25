# 📚 PDF Page Merger

**PDF Page Merger** è un'applicazione desktop sviluppata in Python per appassionati di fumetti e manga.
Permette di unire pagine singole in tavole affiancate senza alcuna perdita di contenuto,
ottimizzando la lettura su tablet e schermi larghi.

---

## ✨ Funzionalità

**Dual Mode**
Scegli la direzione di lettura prima di avviare il merge:
- **Orientale** — Destra → Sinistra, ideale per manga
- **Occidentale** — Sinistra → Destra, per comic e documenti

**Gestione Multi-File**
Carica più PDF contemporaneamente e riordinali con i tasti ▲/▼ prima dell'elaborazione.

**Selective Merging**
Per ogni file puoi definire tramite slider l'intervallo esatto di pagine da affiancare.
Le pagine fuori range (es. copertine, crediti) e le pagine dispari rimangono singole: nessun contenuto viene perso.

**Esclusione Pagine**
Il tasto `...` su ogni file apre un dialogo per escludere pagine specifiche o intervalli dal merging (es. `1, 3-5, 10`). Il tasto diventa arancione quando sono presenti esclusioni attive.

**Info File**
Accanto al nome di ogni PDF viene mostrato il numero totale di pagine del documento.

**Drag & Drop**
Trascina i file PDF direttamente nella finestra. Supportato su Windows, macOS e Linux.

**Organizzazione Automatica**
I file elaborati vengono salvati in `Documenti/pdf-page-merger/` con il suffisso `- ORIENTALE` o `- OCCIDENTALE`.

---

## 🖥️ Compatibilità

| Sistema Operativo | Architetture supportate |
|---|---|
| Windows | x86, x64 |
| macOS | Intel (x86_64), Apple Silicon (arm64) |
| Linux | x86, x86_64, ARM64 |

---

## 🚀 Installazione

### Prerequisiti

- **Python 3.10** o superiore

### 1. Crea un ambiente virtuale

```bash
python -m venv .venv
```

### 2. Attivalo

```bash
# Windows
.\.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Installa le dipendenze

```bash
pip install -r requirements.txt
```

**Dipendenze (`requirements.txt`):**

| Libreria | Descrizione |
|---|---|
| `customtkinter` | Interfaccia grafica moderna |
| `pymupdf` | Motore di elaborazione PDF |
| `tkinterdnd2` | Supporto Drag & Drop nativo |
| `ctkmessagebox` | Finestre di dialogo |

---

## 🛠️ Utilizzo

### Avvio

```bash
python main.py
```

### Flusso di lavoro

1. **Carica** i PDF trascinandoli nell'area di rilascio oppure tramite il tasto **"Seleziona File"**
2. **Riordina** i file con ▲/▼ se necessario
3. **Configura** ogni file:
   - Usa gli **slider** per definire l'intervallo di pagine da affiancare
   - Usa **`...`** per escludere pagine specifiche o intervalli (es. `1, 3-5, 10`)
4. **Scegli** la modalità **Orientale** o **Occidentale**
5. **Avvia** con il tasto **MERGE PDF**

I file risultanti si trovano in `Documenti/pdf-page-merger/`.
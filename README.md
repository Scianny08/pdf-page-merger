# 📚 PDF Page Merger

**PDF Page Merger** è un'applicazione desktop sviluppata in Python per appassionati di fumetti e manga.
Permette di unire pagine singole in tavole affiancate senza alcuna perdita di contenuto,
ottimizzando la lettura su tablet e schermi larghi.

---

## ✨ Funzionalità

**Dual Mode**
Scegli la direzione di lettura prima di avviare il merge:
- **Eastern** — Destra → Sinistra, ideale per manga
- **Western** — Sinistra → Destra, per comic e documenti

**Gestione Multi-File**
Carica più PDF contemporaneamente. Riordinali con i tasti `Up` / `Down` oppure trascinandoli tramite la maniglia `:::` a sinistra di ogni riga.

**Selective Merging**
Per ogni file puoi definire tramite slider l'intervallo esatto di pagine da affiancare.
Le pagine fuori range (copertine, crediti) e le pagine dispari rimangono singole: nessun contenuto viene perso.

**Esclusione Pagine**
Il tasto `Remove Pages` apre un dialogo per rimuovere completamente pagine specifiche o intervalli dall'output (es. `1, 3-5, 10`). Il tasto diventa arancione quando sono presenti esclusioni attive.

**Keep Single**
Il tasto `Keep Single` permette di indicare pagine che devono restare singole nell'output senza essere escluse: agiscono come barriera di accoppiamento su entrambi i lati. Il tasto diventa verde quando è attivo.

**Anteprima Merge**
Il tasto `Preview` su ogni file apre una finestra che mostra una miniatura di ogni tavola che verrà prodotta, navigabile con i tasti freccia o la rotella del mouse.

**Compressione Output**
Seleziona il livello di compressione del PDF risultante tra tre preset: `None`, `Medium`, `High`.

**Cartella di Output Personalizzabile**
La destinazione predefinita è `Documenti/pdf-page-merger/`. Puoi cambiarla con il tasto `Change`. I file vengono salvati con il suffisso `- EASTERN` o `- WESTERN`.

**Undo / Redo**
Tutte le modifiche alla lista sono reversibili con `Ctrl+Z` (Undo) e `Ctrl+Y` / `Ctrl+Shift+Z` (Redo), fino a 25 passi.

**Drag & Drop**
Trascina i file PDF direttamente nell'area di rilascio. Supportato su Windows, macOS e Linux.

**Rilevamento Duplicati**
I file già presenti nella lista non vengono aggiunti una seconda volta.

**Barre di Progresso Doppie**
Durante il merge vengono mostrate due barre: una per il file corrente, una per il progresso complessivo del batch.

**Log degli Errori**
In caso di errori parziali, un dialogo dedicato elenca i file non elaborati con il relativo messaggio di errore. Il merge degli altri file prosegue normalmente.

**Tema Light / Dark**
Il tasto `Switch to Light / Switch to Dark` in alto a destra alterna il tema dell'interfaccia.

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

### 1. Clona o scarica il progetto

```bash
git clone https://github.com/tuo-utente/pdf-page-merger.git
cd pdf-page-merger
```

### 2. Crea un ambiente virtuale

```bash
python -m venv .venv
```

### 3. Attivalo

```bash
# Windows
.\.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 4. Installa le dipendenze

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
| `Pillow` | Gestione immagini e icona |

---

## 🛠️ Utilizzo

### Avvio

```bash
python main.py
```

### Flusso di lavoro

1. **Carica** i PDF trascinandoli nell'area di rilascio oppure con il tasto **Browse Files**
2. **Riordina** i file con `Up` / `Down` o trascinando la maniglia `:::`
3. **Configura** ogni file:
   - Usa gli **slider** per definire l'intervallo di pagine da affiancare
   - Usa **`Remove Pages`** per escludere pagine specifiche o intervalli (es. `1, 3-5, 10`)
   - Usa **`Keep Single`** per pagine che devono restare isolate senza essere rimosse
   - Usa **`Preview`** per verificare il risultato prima del merge
4. **Scegli** la modalità **Eastern** o **Western**
5. **Scegli** il livello di **compressione** output
6. **Avvia** con il tasto **MERGE PDF**

I file risultanti si trovano nella cartella di output selezionata (default: `Documenti/pdf-page-merger/`).
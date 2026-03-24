# 📚 PDF Page Merger

**PDF Page Merger** è un'applicazione desktop moderna e intuitiva
sviluppata in Python.\
È stata progettata specificamente per appassionati di fumetti e manga
che desiderano ottimizzare la propria esperienza di lettura su tablet o
schermi grandi, permettendo di unire pagine singole in tavole affiancate
senza alcuna perdita di dati.

------------------------------------------------------------------------

## ✨ Caratteristiche Principali

### Dual Mode (Lettura Dinamica)

-   **Orientale:** Affiancamento Destra → Sinistra (ideale per Manga).
-   **Occidentale:** Affiancamento Sinistra → Destra (Comic classici,
    libri, documenti).

### Gestione Avanzata Multi-File

Carica più PDF contemporaneamente e decidi l'ordine di fusione tramite i
tasti di riordinamento (▲/▼).

### Selective Merging

Grazie agli slider grafici, puoi definire un intervallo preciso di
pagine da affiancare.

### Zero Data Loss

Le pagine al di fuori del range selezionato o le pagine "solitarie"
(dispari) vengono mantenute come pagine singole. Nessun contenuto viene
eliminato.

### Organizzazione Automatica

I file elaborati vengono salvati automaticamente nella cartella:

`Documenti/pdf-page-merger`

mantenendo il sistema pulito e ordinato.

### Interfaccia Moderna

UI basata su **CustomTkinter** con supporto nativo al Drag & Drop.

------------------------------------------------------------------------

## 🚀 Installazione

### 1. Prerequisiti

Assicurati di avere **Python 3.10** o superiore installato sul tuo
sistema.

### 2. Setup Ambiente Virtuale

È consigliato isolare le dipendenze per evitare conflitti:

``` powershell
# Creazione ambiente
python -m venv .venv

# Attivazione (Windows)
.\.venv\Scripts\activate

# Attivazione (Linux/macOS)
source .venv/bin/activate
```

### 3. Installazione Dipendenze

Installa le librerie necessarie tramite il file `requirements.txt`:

``` powershell
pip install -r requirements.txt
```

**Contenuto di requirements.txt:**

-   `customtkinter` --- Interfaccia grafica
-   `pymupdf` --- Motore di elaborazione PDF
-   `tkinterdnd2` --- Supporto Drag & Drop
-   `ctkmessagebox` --- Pop-up di sistema

------------------------------------------------------------------------

## 🛠️ Guida all'uso

**Avvio:**\
Esegui:

``` bash
python main.py
```

**Caricamento:**\
Trascina i tuoi file PDF nell'area di rilascio o usa il tasto
**"Seleziona File"**.

**Configurazione:**

-   Scegli lo stile (**Orientale** o **Occidentale**).
-   Usa le frecce ▲/▼ per ordinare i capitoli/file.
-   Regola gli slider per ogni file per decidere quali pagine
    affiancare\
    (es. escludi la copertina impostando l'inizio a pagina 2).

**Esecuzione:**\
Clicca su **MERGE PDF**.

**Risultato:**\
Troverai il file finale nella tua cartella utente sotto:

`Documenti/pdf-page-merger`

con il suffisso:

-   `- ORIENTALE`
-   `- OCCIDENTALE`

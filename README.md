# 📚 PDF Fusion

Un'applicazione desktop moderna e performante scritta in **Python** per
l'unione intelligente di pagine PDF. Progettata per i lettori di fumetti
e manga, permette di affiancare le pagine rispettando il senso di
lettura scelto senza perdere l'integrità del documento originale.

------------------------------------------------------------------------

## ✨ Caratteristiche Principali

-   **Dual Mode (Lettura Dinamica):**
    -   **Manga Style:** Affiancamento Destra → Sinistra (Giapponese).
    -   **Western Style:** Affiancamento Sinistra → Destra
        (Europeo/Americano).
-   **Gestione Intelligente dei Range:** Seleziona un intervallo
    specifico di pagine da unire tramite slider grafici.
-   **Zero Data Loss:** Le pagine esterne al range selezionato e le
    eventuali pagine solitarie (dispari) vengono mantenute come pagine
    singole nel file finale. **Nessuna pagina viene scartata.**
-   **Interfaccia Moderna:** UI basata su `CustomTkinter` con pieno
    supporto al **Drag & Drop** dei file.
-   **Architettura Robusta:** Fix automatico per il mismatch dei driver
    Tcl/Tk (32/64 bit) su Windows.

------------------------------------------------------------------------

## 🚀 Installazione Rapida

### 1. Prerequisiti

Assicurati di avere **Python 3.10** o superiore installato.

### 2. Setup Ambiente

Si consiglia vivamente l'uso di un ambiente virtuale per evitare
conflitti tra librerie:

``` powershell
# Creazione ambiente
python -m venv .venv

# Attivazione (Windows)
.\.venv\Scripts\activate
```

### 3. Installazione Dipendenze

Tutte le librerie necessarie sono elencate nel file `requirements.txt`.
Installale con un unico comando:

``` powershell
pip install -r requirements.txt
```

------------------------------------------------------------------------

## 🛠️ Guida all'uso

**Avvio:** Esegui il comando `python main.py`.

**Caricamento:** Trascina un file PDF nell'area azzurra o clicca su
"Seleziona File Manualmente".

**Configurazione:**

-   Scegli lo Stile (Manga per i fumetti orientali, Occidentale per i
    comic classici).
-   Regola gli Slider per definire il range di pagine che vuoi
    effettivamente "unire".

**Esecuzione:** Clicca su **ELABORA DOCUMENTO**.

**Risultato:** Il file generato apparirà nella stessa cartella del file
sorgente con il suffisso `_manga` o `_occidentale`.


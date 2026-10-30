"""Importatore dello storico spese dal file Excel (.xlsx) verso Supabase.

Modulo di dominio puro, indipendente da Streamlit e Supabase.

- `leggi_storico_excel`: legge un file `.xlsx` dello storico spese con pandas
  (engine `openpyxl`), valida la presenza delle colonne attese e ritorna le
  righe mappate insieme all'elenco delle colonne eventualmente mancanti.

- `mappa_riga_a_movimento`: mappa una riga dello storico sui campi del
  Movimento, convertendo `Guadagni/Spese` nel Tipo_Movimento e ritornando
  `None` se mancano campi obbligatori (Req 3.1, 3.4).

- `importa_storico`: orchestra la preparazione dell'import: legge le righe,
  le mappa, crea (logicamente, delegando al layer dati) i conti/categorie/
  sotto-categorie mancanti, prepara i record per l'upsert idempotente sulla
  Chiave_Naturale_Movimento e ritorna il riepilogo
  `{importati, ignorati_presenti, scartati}` (Req 3.5, 3.6, 3.7, 3.9).
"""

import math

import pandas as pd

from spese.normalizza import chiave_naturale_movimento
from utils import _to_iso

# Colonne attese nello schema dello storico spese Excel (Req 3.1).
COLONNE_ATTESE = [
    "Periodo",
    "Conto",
    "Categoria",
    "Sotto-categoria",
    "Nota",
    "EUR",
    "Guadagni/Spese",
    "Descrizione",
    "Valuta",
]


class ExcelNonValido(Exception):
    """Errore gestito: il file caricato non è un `.xlsx` valido/leggibile.

    Viene sollevato da `leggi_storico_excel` quando il file non può essere letto
    come foglio Excel. La UI intercetta questa eccezione per interrompere
    l'import senza salvare alcun Movimento e mostrare un messaggio all'Utente
    (Req 3.2).
    """


def leggi_storico_excel(file) -> tuple[list[dict], list[str]]:
    """Legge lo storico spese da un file `.xlsx` e valida le colonne attese.

    Il file viene letto con pandas (engine `openpyxl`). La funzione non salva
    nulla: si limita a leggere e mappare le righe sulle colonne attese.

    Comportamento rispetto ai requisiti:

    - Se il file non può essere letto come `.xlsx` valido, viene sollevato
      `ExcelNonValido`, un errore gestito dalla UI che interrompe l'import senza
      salvare alcun Movimento (Req 3.2).
    - Se mancano una o più colonne attese (`COLONNE_ATTESE`), `colonne_mancanti`
      è non vuoto e `righe_mappate` è una lista vuota: l'import non prosegue e la
      UI segnala le colonne mancanti (Req 3.3).
    - Se tutte le colonne attese sono presenti, `righe_mappate` contiene un dict
      per ogni riga del foglio, con chiavi pari ai nomi di `COLONNE_ATTESE`
      (Req 3.1). La mappatura sui campi del Movimento avviene in
      `mappa_riga_a_movimento` (task 7.2).

    Args:
        file: Percorso del file, oggetto file-like (es. l'output di
            `st.file_uploader`) o buffer di byte contenente un `.xlsx`.

    Returns:
        Una tupla `(righe_mappate, colonne_mancanti)` dove:
        - `righe_mappate` è la lista dei dizionari riga (vuota se mancano
          colonne attese);
        - `colonne_mancanti` è la lista delle colonne attese assenti dal file,
          nell'ordine di `COLONNE_ATTESE` (vuota se sono tutte presenti).

    Raises:
        ExcelNonValido: se il file non è leggibile come `.xlsx` valido.
    """
    try:
        df = pd.read_excel(file, engine="openpyxl")
    except Exception as exc:  # file non valido / illeggibile come xlsx (Req 3.2)
        raise ExcelNonValido(
            "Impossibile leggere il file: non è un file .xlsx valido."
        ) from exc

    # Nomi colonna normalizzati a stringa per un confronto robusto.
    colonne_presenti = [str(c) for c in df.columns]

    # Colonne attese assenti, mantenendo l'ordine di COLONNE_ATTESE (Req 3.3).
    colonne_mancanti = [c for c in COLONNE_ATTESE if c not in colonne_presenti]
    if colonne_mancanti:
        return [], colonne_mancanti

    # Tutte le colonne attese presenti: estrai solo quelle attese, nell'ordine
    # canonico, e produci un dict per riga (Req 3.1).
    df_attese = df[COLONNE_ATTESE]
    righe_mappate = df_attese.to_dict(orient="records")

    return righe_mappate, []


# Insieme dei Tipo_Movimento ammessi, coerente con il Glossary (Req 2.5) e con
# il CHECK della tabella `movimenti`. La colonna storica "Guadagni/Spese"
# contiene direttamente questi valori.
TIPI_MOVIMENTO_VALIDI = frozenset({
    "Spese",
    "In",
    "Trasferimento ingresso",
    "Trasferimento uscita",
    "Aumento Saldo",
    "Decremento Saldo",
})

# Valuta predefinita quando la colonna "Valuta" è assente o vuota (Req 2.9).
VALUTA_DEFAULT = "EUR"


def _pulisci_opzionale(valore):
    """Normalizza un campo facoltativo a `str` non vuota oppure `None`.

    Tratta i valori mancanti di pandas (`NaN`/`NaT`/`None`) e le stringhe vuote
    (dopo strip) come assenza di valore, ritornando `None`. Altrimenti ritorna
    la rappresentazione testuale ripulita dagli spazi ai bordi.
    """
    if valore is None:
        return None
    try:
        if pd.isna(valore):
            return None
    except (TypeError, ValueError):
        # Valori non scalari (improbabili qui): trattali come presenti.
        pass
    testo = str(valore).strip()
    return testo or None


def _importo_a_float(valore):
    """Converte l'importo della colonna EUR in `float` finito oppure `None`.

    Accetta sia numeri sia stringhe con separatori italiani (es. "1.234,56").
    Ritorna `None` se il valore è mancante o non convertibile a un `float`
    finito (sono respinti `NaN` e `±inf`).
    """
    if valore is None or isinstance(valore, bool):
        return None
    try:
        if pd.isna(valore):
            return None
    except (TypeError, ValueError):
        pass
    # Percorso numerico diretto.
    if isinstance(valore, (int, float)):
        importo = float(valore)
    else:
        testo = str(valore).strip()
        if not testo:
            return None
        # Normalizza i separatori in stile italiano: "1.234,56" -> "1234.56".
        if "," in testo:
            testo = testo.replace(".", "").replace(",", ".")
        try:
            importo = float(testo)
        except (TypeError, ValueError):
            return None
    if math.isnan(importo) or math.isinf(importo):
        return None
    return round(importo, 2)


def mappa_riga_a_movimento(riga: dict) -> dict | None:
    """Mappa una riga dello storico Excel sui campi del Movimento.

    La funzione è DETERMINISTICA (Property 5): per la stessa riga in ingresso
    produce sempre lo stesso movimento. Mappa le colonne storiche sui campi del
    Movimento secondo la corrispondenza:

    - `Periodo`          -> `data_movimento` (ISO `YYYY-MM-DD` via `_to_iso`)
    - `Conto`            -> `conto`
    - `Categoria`        -> `categoria` (facoltativo)
    - `Sotto-categoria`  -> `sotto_categoria` (facoltativo)
    - `Nota`             -> `nota` (facoltativo)
    - `EUR`              -> `importo_eur`
    - `Guadagni/Spese`   -> `tipo_movimento`
    - `Descrizione`      -> `descrizione` (facoltativo)
    - `Valuta`           -> `valuta` (default `EUR` se assente, Req 2.9)

    Il valore della colonna `Guadagni/Spese` è già un Tipo_Movimento del
    Glossary e viene usato come tale; se non appartiene a
    `TIPI_MOVIMENTO_VALIDI` la riga è considerata non valida.

    Ritorna `None` se manca uno dei campi obbligatori del Movimento (Req 3.4),
    ovvero quando:

    - `data_movimento` non è ricavabile da `Periodo`;
    - `conto` è assente o vuoto;
    - `importo_eur` è assente o non convertibile a `float` finito;
    - `tipo_movimento` è assente o non appartiene a `TIPI_MOVIMENTO_VALIDI`.

    La valuta non è obbligatoria: se assente viene impostata a `EUR`.

    Args:
        riga: Dizionario di una riga dello storico, con chiavi pari ai nomi di
            `COLONNE_ATTESE` (così come prodotto da `leggi_storico_excel`).

    Returns:
        Un dizionario con i campi del Movimento, oppure `None` se mancano campi
        obbligatori.
    """
    if not isinstance(riga, dict):
        return None

    # --- Campi obbligatori ---
    # data_movimento da Periodo (Timestamp/datetime/str -> ISO).
    data_movimento = _to_iso(riga.get("Periodo"))
    if not data_movimento:
        return None

    # conto obbligatorio e non vuoto.
    conto = _pulisci_opzionale(riga.get("Conto"))
    if not conto:
        return None

    # importo_eur obbligatorio, numerico e finito.
    importo_eur = _importo_a_float(riga.get("EUR"))
    if importo_eur is None:
        return None

    # tipo_movimento obbligatorio e appartenente al Glossary.
    tipo_movimento = _pulisci_opzionale(riga.get("Guadagni/Spese"))
    if tipo_movimento not in TIPI_MOVIMENTO_VALIDI:
        return None

    # --- Campo con default ---
    valuta = _pulisci_opzionale(riga.get("Valuta")) or VALUTA_DEFAULT

    # --- Campi facoltativi ---
    categoria = _pulisci_opzionale(riga.get("Categoria"))
    sotto_categoria = _pulisci_opzionale(riga.get("Sotto-categoria"))
    nota = _pulisci_opzionale(riga.get("Nota"))
    descrizione = _pulisci_opzionale(riga.get("Descrizione"))

    return {
        "data_movimento": data_movimento,
        "conto": conto,
        "categoria": categoria,
        "sotto_categoria": sotto_categoria,
        "nota": nota,
        "importo_eur": importo_eur,
        "tipo_movimento": tipo_movimento,
        "descrizione": descrizione,
        "valuta": valuta,
    }


def _import_database_module():
    """Importa pigramente il modulo `database` (layer dati Supabase).

    L'import è ritardato al momento dell'uso in modo che `excel_importer` resti
    importabile e testabile anche se `database` (o le sue funzioni del task
    10.x) non è ancora disponibile o non è configurato. Le funzioni del layer
    dati sono comunque iniettabili in `importa_storico`, quindi questo import è
    solo il comportamento di default.
    """
    import database  # import locale: nessuna dipendenza a import-time

    return database


def _delega(funzione, nome_attributo):
    """Risolve una callable di delega al layer dati.

    Se `funzione` è fornita (iniettata, utile per i test) viene usata così
    com'è. Altrimenti si recupera l'attributo `nome_attributo` dal modulo
    `database` importato pigramente.
    """
    if funzione is not None:
        return funzione
    return getattr(_import_database_module(), nome_attributo)


def importa_storico(
    file,
    *,
    get_or_create_conto=None,
    upsert_categoria=None,
    upsert_sotto_categoria=None,
    upsert_movimenti=None,
) -> dict:
    """Orchestra la preparazione e l'import dello storico spese da un `.xlsx`.

    Orchestrazione di sola preparazione (il salvataggio idempotente è
    delegato al layer dati): legge il file, mappa ogni riga, crea i
    conti/categorie/sotto-categorie mancanti delegando al layer dati
    (Req 3.5, 3.6), prepara i record con la `descrizione_normalizzata` della
    Chiave_Naturale_Movimento pronti per l'upsert idempotente (Req 3.7) e
    ritorna un riepilogo con i conteggi (Req 3.9).

    Flusso:

    1. `leggi_storico_excel(file)` legge il foglio e valida le colonne attese.
       Se mancano colonne attese (`colonne_mancanti` non vuoto) l'import non
       prosegue: viene restituito un riepilogo a zero importati, con tutte le
       righe eventualmente lette conteggiate come scartate (coerente con il
       fatto che senza colonne attese non c'è nulla da importare). Se il file
       non è un `.xlsx` valido, `leggi_storico_excel` solleva `ExcelNonValido`,
       che la UI gestisce (Req 3.2): qui l'eccezione è lasciata propagare.
    2. Per ogni riga, `mappa_riga_a_movimento` produce un movimento oppure
       `None`. Le righe mappate a `None` (mancano campi obbligatori) sono
       conteggiate tra gli `scartati` (Req 3.4) e non vengono preparate.
    3. Per ogni movimento valido si calcola la Chiave_Naturale_Movimento
       (data, conto, importo_eur, descrizione_normalizzata). Se la chiave non è
       calcolabile il movimento è scartato; altrimenti il movimento è arricchito
       con `descrizione_normalizzata` ed è candidato all'upsert.
    4. Si creano, delegando al layer dati, i conti e le categorie/sotto-categorie
       mancanti richiamati dai movimenti validi (Req 3.5, 3.6). La creazione è
       idempotente lato dati (upsert su chiave naturale), quindi è sicuro
       invocarla per ogni valore distinto incontrato.
    5. Si delega l'upsert idempotente dei movimenti al layer dati (Req 3.7). Il
       numero di movimenti effettivamente inseriti e di quelli ignorati perché
       già presenti è determinato dall'esito dell'upsert idempotente (Req 3.8):
       se il layer dati riporta il conteggio degli inseriti, `importati` e
       `ignorati_presenti` sono valorizzati di conseguenza; in assenza di tale
       informazione tutti i movimenti preparati sono contati come `importati` e
       `ignorati_presenti` resta 0.

    La funzione è orientata alla pura orchestrazione: tutte le interazioni con
    il database avvengono tramite callable iniettabili. Di default queste
    callable sono risolte dal modulo `database` (importato pigramente), così il
    modulo resta importabile anche se il layer dati del task 10.x non è ancora
    presente.

    Args:
        file: Percorso, oggetto file-like o buffer di byte del `.xlsx` da
            importare (come accettato da `leggi_storico_excel`).
        get_or_create_conto: Callable `(nome: str) -> Any` che garantisce
            l'esistenza di un Conto e ne ritorna l'identificativo. Se `None`,
            viene usata `database.get_or_create_conto`.
        upsert_categoria: Callable `(nome: str) -> Any` che garantisce
            l'esistenza di una Categoria. Se `None`, usa
            `database.upsert_categoria`.
        upsert_sotto_categoria: Callable `(nome: str, categoria: str) -> Any`
            che garantisce l'esistenza di una Sotto_Categoria legata alla sua
            Categoria. Se `None`, usa `database.upsert_sotto_categoria`.
        upsert_movimenti: Callable `(movimenti: list[dict]) -> Any` che esegue
            l'upsert idempotente dei movimenti sulla Chiave_Naturale_Movimento.
            Se `None`, usa `database.upsert_movimenti`. Può ritornare un intero
            (numero di movimenti inseriti) usato per distinguere importati da
            ignorati; qualsiasi altro valore è trattato come "conteggio non
            disponibile".

    Returns:
        Un dizionario di riepilogo `{"importati": int, "ignorati_presenti": int,
        "scartati": int}` (Req 3.9). Vale sempre l'invariante:
        `importati + ignorati_presenti + scartati == righe totali lette`, con 0
        per le categorie prive di elementi.

    Raises:
        ExcelNonValido: se il file non è leggibile come `.xlsx` valido (Req 3.2).
    """
    righe, colonne_mancanti = leggi_storico_excel(file)

    # Colonne attese mancanti: nessun import possibile (Req 3.3). `righe` è una
    # lista vuota in questo caso, quindi il riepilogo resta a zero.
    if colonne_mancanti:
        return {
            "importati": 0,
            "ignorati_presenti": 0,
            "scartati": len(righe),
        }

    scartati = 0
    movimenti_validi: list[dict] = []

    for riga in righe:
        movimento = mappa_riga_a_movimento(riga)
        if movimento is None:
            # Campi obbligatori mancanti -> riga scartata (Req 3.4).
            scartati += 1
            continue

        # Calcola la Chiave_Naturale_Movimento; senza chiave non è possibile
        # l'upsert idempotente, quindi la riga è scartata.
        chiave = chiave_naturale_movimento(
            movimento.get("data_movimento"),
            movimento.get("conto"),
            movimento.get("importo_eur"),
            movimento.get("descrizione"),
        )
        if chiave is None:
            scartati += 1
            continue

        record = dict(movimento)
        record["descrizione_normalizzata"] = chiave[3]
        movimenti_validi.append(record)

    # Nessun movimento valido: riepilogo immediato (evita import del layer dati).
    if not movimenti_validi:
        return {
            "importati": 0,
            "ignorati_presenti": 0,
            "scartati": scartati,
        }

    # Risolvi le callable di delega al layer dati (lazy di default).
    _get_or_create_conto = _delega(get_or_create_conto, "get_or_create_conto")
    _upsert_categoria = _delega(upsert_categoria, "upsert_categoria")
    _upsert_sotto_categoria = _delega(
        upsert_sotto_categoria, "upsert_sotto_categoria"
    )
    _upsert_movimenti = _delega(upsert_movimenti, "upsert_movimenti")

    # 4. Crea (idempotentemente) conti/categorie/sotto-categorie mancanti
    #    delegando al layer dati (Req 3.5, 3.6). Si itera sui valori distinti.
    conti_visti: set[str] = set()
    categorie_viste: set[str] = set()
    sotto_categorie_viste: set[tuple[str, str]] = set()

    for movimento in movimenti_validi:
        conto = movimento.get("conto")
        if conto and conto not in conti_visti:
            conti_visti.add(conto)
            _get_or_create_conto(conto)

        categoria = movimento.get("categoria")
        if categoria and categoria not in categorie_viste:
            categorie_viste.add(categoria)
            _upsert_categoria(categoria)

        sotto_categoria = movimento.get("sotto_categoria")
        # Una Sotto_Categoria ha senso solo se legata a una Categoria (Req 2.4).
        if categoria and sotto_categoria:
            coppia = (categoria, sotto_categoria)
            if coppia not in sotto_categorie_viste:
                sotto_categorie_viste.add(coppia)
                _upsert_sotto_categoria(sotto_categoria, categoria)

    # 5. Delega l'upsert idempotente dei movimenti (Req 3.7, 3.8).
    esito = _upsert_movimenti(movimenti_validi)

    totale_preparati = len(movimenti_validi)
    if isinstance(esito, int) and not isinstance(esito, bool):
        # Il layer dati riporta quanti movimenti sono stati effettivamente
        # inseriti: i restanti erano già presenti e sono stati ignorati (Req 3.8).
        importati = max(0, min(esito, totale_preparati))
        ignorati_presenti = totale_preparati - importati
    else:
        # Conteggio inserimenti non disponibile: tutti i preparati sono contati
        # come importati, nessun già-presente determinabile da qui.
        importati = totale_preparati
        ignorati_presenti = 0

    return {
        "importati": importati,
        "ignorati_presenti": ignorati_presenti,
        "scartati": scartati,
    }

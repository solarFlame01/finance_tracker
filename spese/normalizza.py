"""Normalizzazione dell'esercente e calcolo della chiave naturale del movimento.

Modulo di dominio puro, indipendente da Streamlit e Supabase.

- `normalize_esercente`: regola DETERMINISTICA e IDEMPOTENTE di normalizzazione
  dell'esercente a partire dalla descrizione di una transazione. Viene usata
  identica in scrittura e in lettura del Mapping_Esercente_Categoria (Req 6.8).

`chiave_naturale_movimento` sarà aggiunta nel task 4.2.
"""

import math
import re

from unidecode import unidecode

# Token di rumore che compaiono come prefisso/parola isolata negli estratti conto.
# Vengono rimossi come parole intere (non come sottostringhe) per non intaccare
# nomi di esercente legittimi.
_NOISE_TOKENS = frozenset({
    "pos",
    "pagamento",
    "pag",
    "pagam",
    "carta",
    "cartasi",
    "addebito",
    "addebito diretto",
    "bonifico",
    "prelievo",
    "prelevamento",
    "acquisto",
    "operazione",
    "op",
    "contactless",
    "ecommerce",
    "e-commerce",
    "sepa",
    "sdd",
    "autorizzazione",
    "aut",
    "auth",
    "rif",
    "riferimento",
    "num",
    "numero",
    "data",
    "ore",
    "ora",
    "del",
    "il",
})

# Codici di valuta/stato spesso presenti in coda alle descrizioni (es. "... ita").
_TRAILING_STATES = frozenset({
    "ita", "it", "italia", "usa", "us", "gbr", "gb", "esp", "es", "fra", "fr",
    "deu", "de", "nld", "nl", "che", "ch", "irl", "ie", "eur", "usd", "gbp",
})

# Data in vari formati: 01/02/2024, 1-2-24, 2024.01.02, ecc.
_RE_DATE = re.compile(
    r"\b\d{1,4}[/.\-]\d{1,2}([/.\-]\d{1,4})?\b"
)
# Orario: 12:30 oppure 12:30:45
_RE_TIME = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b")
# Importi/numeri di autorizzazione lunghi (3+ cifre) o con separatori decimali.
_RE_LONG_NUMBER = re.compile(r"\b\d[\d.,]{2,}\b")
# Collasso di spazi multipli.
_RE_MULTISPACE = re.compile(r"\s+")
# Tutto ciò che non è lettera/cifra/spazio diventa spazio.
_RE_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")


def normalize_esercente(descrizione: str) -> str:
    """Normalizza l'esercente a partire dalla descrizione di una transazione.

    Regola deterministica (Req 6.8), coerente con `clean_col_name` di `utils.py`
    (stessa base: `unidecode` -> minuscolo -> strip):

    1. `unidecode` per rimuovere accenti e caratteri non ASCII.
    2. Lowercasing e strip.
    3. Rimozione di date, orari e numeri lunghi (importi, numeri di
       autorizzazione/protocollo).
    4. Sostituzione dei caratteri non alfanumerici con spazio.
    5. Collasso degli spazi multipli.
    6. Rimozione dei token di rumore noti (es. "pos", "pagamento", "carta").
    7. Rimozione dei codici stato/valuta finali (es. "ita", "eur").
    8. Collasso finale degli spazi e strip.

    La funzione è idempotente: `normalize_esercente(normalize_esercente(x))`
    produce lo stesso risultato di `normalize_esercente(x)`.

    Args:
        descrizione: Testo descrittivo grezzo della transazione. Valori `None`
            o non stringa vengono trattati come stringa vuota/convertiti con
            `str`.

    Returns:
        L'esercente normalizzato, eventualmente stringa vuota se la descrizione
        non contiene informazione utile dopo la pulizia.
    """
    if descrizione is None:
        return ""

    # 1-2. unidecode -> minuscolo -> strip (coerente con clean_col_name).
    testo = unidecode(str(descrizione)).lower().strip()

    # 3. Rimuovi date, orari e numeri lunghi prima di distruggere i separatori.
    testo = _RE_DATE.sub(" ", testo)
    testo = _RE_TIME.sub(" ", testo)
    testo = _RE_LONG_NUMBER.sub(" ", testo)

    # 4. Non alfanumerici -> spazio.
    testo = _RE_NON_ALNUM.sub(" ", testo)

    # 5. Collasso spazi multipli.
    testo = _RE_MULTISPACE.sub(" ", testo).strip()

    if not testo:
        return ""

    # 6. Rimozione dei token di rumore (parole intere).
    parole = [p for p in testo.split(" ") if p and p not in _NOISE_TOKENS]

    # 7. Rimozione dei codici stato/valuta finali (anche ripetuti in coda).
    while parole and parole[-1] in _TRAILING_STATES:
        parole.pop()

    # 8. Collasso finale (lo split/join normalizza già gli spazi) e strip.
    return " ".join(parole).strip()

def chiave_naturale_movimento(data_iso: str, conto: str, importo_eur: float,
                              descrizione: str) -> tuple[str, str, float, str] | None:
    """Calcola la Chiave_Naturale_Movimento di un movimento.

    La chiave naturale identifica univocamente un movimento ai fini della
    deduplicazione ed è la tupla:

        (data, conto, importo_eur arrotondato a 2 decimali, descrizione_normalizzata)

    dove ``descrizione_normalizzata = normalize_esercente(descrizione)``.

    Ritorna ``None`` se un componente obbligatorio manca o non è calcolabile
    (Req 5.3), ovvero quando:

    - ``data_iso`` è assente o vuota (dopo strip);
    - ``conto`` è assente o vuoto (dopo strip);
    - ``importo_eur`` è assente o non convertibile a ``float`` finito
      (sono respinti anche ``NaN`` e ``±inf``);
    - ``descrizione`` normalizza a stringa vuota.

    Args:
        data_iso: Data del movimento in formato ISO (stringa). Usata così com'è
            dopo lo strip; non viene riparsata.
        conto: Identificativo/nome del conto. Usato dopo lo strip.
        importo_eur: Importo in EUR. Convertito a ``float`` e arrotondato a 2
            decimali.
        descrizione: Descrizione grezza della transazione, da cui si ricava
            l'esercente normalizzato tramite ``normalize_esercente``.

    Returns:
        La tupla ``(data, conto, importo_eur, descrizione_normalizzata)`` oppure
        ``None`` se un componente obbligatorio manca o non è calcolabile.
    """
    # data obbligatoria e non vuota
    if data_iso is None:
        return None
    data = str(data_iso).strip()
    if not data:
        return None

    # conto obbligatorio e non vuoto
    if conto is None:
        return None
    conto_norm = str(conto).strip()
    if not conto_norm:
        return None

    # importo obbligatorio, numerico e finito
    if importo_eur is None or isinstance(importo_eur, bool):
        return None
    try:
        importo = float(importo_eur)
    except (TypeError, ValueError):
        return None
    if math.isnan(importo) or math.isinf(importo):
        return None
    importo = round(importo, 2)

    # descrizione obbligatoria: deve normalizzare a non vuoto
    descrizione_normalizzata = normalize_esercente(descrizione)
    if not descrizione_normalizzata:
        return None

    return (data, conto_norm, importo, descrizione_normalizzata)

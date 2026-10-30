# Feature: gestione-spese, Property 5: Mappatura deterministica delle colonne storiche Excel
"""Property-based test per `spese.excel_importer.mappa_riga_a_movimento` (task 7.4).

Property 5: *Per ogni* riga valida dello storico Excel, `mappa_riga_a_movimento`
produce un movimento i cui campi (data, conto, categoria, sotto-categoria, nota,
importo in EUR, tipo movimento, descrizione, valuta) corrispondono esattamente al
mapping definito tra colonne storiche e campi del Movimento:

    Periodo          -> data_movimento (ISO YYYY-MM-DD)
    Conto            -> conto
    Categoria        -> categoria (facoltativo)
    Sotto-categoria  -> sotto_categoria (facoltativo)
    Nota             -> nota (facoltativo)
    EUR              -> importo_eur (arrotondato a 2 decimali)
    Guadagni/Spese   -> tipo_movimento (dal Glossary)
    Descrizione      -> descrizione (facoltativo)
    Valuta           -> valuta (default EUR se assente, Req 2.9)

Si verifica inoltre la DETERMINISMO: la stessa riga in ingresso produce sempre
lo stesso movimento in uscita.

Validates: Requirements 3.1
"""

import datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.excel_importer import (
    TIPI_MOVIMENTO_VALIDI,
    VALUTA_DEFAULT,
    mappa_riga_a_movimento,
)

# ---------------------------------------------------------------------------
# Generatori intelligenti, vincolati allo spazio di input "riga valida".
#
# Ogni componente obbligatorio è generato in forma valida così che la riga
# produca sempre un movimento (non None), isolando la verifica sul mapping.
# ---------------------------------------------------------------------------

# --- Periodo (data) ---------------------------------------------------------
# Usiamo oggetti date/datetime: _to_iso li formatta in modo deterministico
# come "%Y-%m-%d", così l'atteso è calcolabile senza riparsing ambiguo.
_date_valide = st.dates(
    min_value=datetime.date(1990, 1, 1),
    max_value=datetime.date(2100, 12, 31),
)


@st.composite
def _periodi(draw):
    """Genera un valore Periodo (date o datetime) e l'ISO atteso."""
    d = draw(_date_valide)
    if draw(st.booleans()):
        valore = datetime.datetime(d.year, d.month, d.day, draw(st.integers(0, 23)),
                                   draw(st.integers(0, 59)))
    else:
        valore = d
    atteso = d.strftime("%Y-%m-%d")
    return valore, atteso


# --- Conto (obbligatorio, non vuoto dopo strip) -----------------------------
_conti = st.sampled_from([
    "Conto Corrente", "Carta Revolut", "Fineco", "N26", "Libretto",
    "Buddybank", "Widiba",
])

# --- EUR (importo obbligatorio, numerico finito) ----------------------------
# Numeri già "puliti" (float/int) in modo che l'atteso sia round(x, 2).
_importi = st.one_of(
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    st.integers(min_value=-1_000_000, max_value=1_000_000),
)

# --- Guadagni/Spese -> tipo_movimento (dal Glossary) ------------------------
_tipi_movimento = st.sampled_from(sorted(TIPI_MOVIMENTO_VALIDI))

# --- Campi testuali facoltativi: valore non vuoto oppure "assente" ----------
# Testo non vuoto e con bordi "puliti" (niente spazi ai margini) così che
# l'atteso sia esattamente il valore generato.
_testo_pulito = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=0x2FF,
                           blacklist_categories=("Cs", "Cc")),
    min_size=1,
    max_size=40,
).map(lambda s: s.strip()).filter(lambda s: len(s) > 0)

# "Assenza" del campo facoltativo: chiave mancante o valore None/stringa vuota.
_assente = st.sampled_from([None, "", "   "])

# Valuta: codice non vuoto oppure assente (default EUR).
_valute = st.sampled_from(["EUR", "USD", "GBP", "CHF", "JPY"])


@st.composite
def _righe_valide(draw):
    """Genera una riga valida dello storico e il movimento atteso."""
    periodo_valore, data_attesa = draw(_periodi())
    conto = draw(_conti)
    importo = draw(_importi)
    tipo = draw(_tipi_movimento)

    # Facoltativi: a volte presenti (testo pulito), a volte assenti (-> None).
    categoria_in = draw(st.one_of(_testo_pulito, _assente))
    sotto_in = draw(st.one_of(_testo_pulito, _assente))
    nota_in = draw(st.one_of(_testo_pulito, _assente))
    descrizione_in = draw(st.one_of(_testo_pulito, _assente))

    # Valuta: presente (-> se stessa) oppure assente (-> default EUR).
    valuta_presente = draw(st.booleans())
    valuta_in = draw(_valute) if valuta_presente else draw(_assente)

    riga = {
        "Periodo": periodo_valore,
        "Conto": conto,
        "Categoria": categoria_in,
        "Sotto-categoria": sotto_in,
        "Nota": nota_in,
        "EUR": importo,
        "Guadagni/Spese": tipo,
        "Descrizione": descrizione_in,
        "Valuta": valuta_in,
    }

    def _atteso_opzionale(v):
        # Mirroring di _pulisci_opzionale per valori già "puliti":
        # None/stringa vuota (dopo strip) -> None, altrimenti il testo.
        if v is None:
            return None
        testo = str(v).strip()
        return testo or None

    valuta_attesa = _atteso_opzionale(valuta_in) or VALUTA_DEFAULT

    atteso = {
        "data_movimento": data_attesa,
        "conto": conto,
        "categoria": _atteso_opzionale(categoria_in),
        "sotto_categoria": _atteso_opzionale(sotto_in),
        "nota": _atteso_opzionale(nota_in),
        "importo_eur": round(float(importo), 2),
        "tipo_movimento": tipo,
        "descrizione": _atteso_opzionale(descrizione_in),
        "valuta": valuta_attesa,
    }
    return riga, atteso


@settings(max_examples=100)
@given(dati=_righe_valide())
def test_mappatura_corrisponde_esattamente(dati):
    """Ogni campo del movimento corrisponde esattamente al mapping definito."""
    riga, atteso = dati
    movimento = mappa_riga_a_movimento(riga)

    # Una riga valida produce sempre un movimento (non None).
    assert movimento is not None

    # Chiavi esattamente quelle attese dal mapping (niente di più, niente di meno).
    assert set(movimento.keys()) == set(atteso.keys())

    # Mapping campo per campo.
    assert movimento["data_movimento"] == atteso["data_movimento"]
    assert movimento["conto"] == atteso["conto"]
    assert movimento["categoria"] == atteso["categoria"]
    assert movimento["sotto_categoria"] == atteso["sotto_categoria"]
    assert movimento["nota"] == atteso["nota"]
    assert movimento["importo_eur"] == atteso["importo_eur"]
    assert movimento["tipo_movimento"] == atteso["tipo_movimento"]
    assert movimento["tipo_movimento"] in TIPI_MOVIMENTO_VALIDI
    assert movimento["descrizione"] == atteso["descrizione"]
    assert movimento["valuta"] == atteso["valuta"]

    # L'intero movimento coincide con l'atteso.
    assert movimento == atteso


@settings(max_examples=100)
@given(dati=_righe_valide())
def test_determinismo_stessa_riga_stesso_output(dati):
    """Determinismo: la stessa riga -> movimenti uguali su chiamate ripetute."""
    riga, _ = dati
    primo = mappa_riga_a_movimento(dict(riga))
    secondo = mappa_riga_a_movimento(dict(riga))
    assert primo == secondo


@settings(max_examples=100)
@given(dati=_righe_valide())
def test_valuta_default_quando_assente(dati):
    """Quando la colonna Valuta è assente/vuota, la valuta è EUR (Req 2.9)."""
    riga, _ = dati
    riga_senza_valuta = dict(riga)
    riga_senza_valuta["Valuta"] = None
    movimento = mappa_riga_a_movimento(riga_senza_valuta)
    assert movimento is not None
    assert movimento["valuta"] == VALUTA_DEFAULT

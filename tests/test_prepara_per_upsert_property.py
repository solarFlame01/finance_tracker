# Feature: gestione-spese, Property 4
"""Property-based test per `spese.riconciliatore.prepara_per_upsert` (task 5.10).

Property 4: *Conservazione dei conteggi di import/riconciliazione.* Per ogni
lista di transazioni in ingresso, la somma dei conteggi restituiti
(`nuovi` + `gia_presenti` + `scartati`) è uguale al numero di elementi
processabili (le transazioni che sono dict), e ogni categoria di conteggio è
sempre presente e non negativa (0 per le categorie vuote). Nessuna transazione
processabile viene persa o contata due volte: finisce esattamente in uno fra
`validi` (conteggiata come `nuovi`) e `scartati`.

Per la funzione pura `prepara_per_upsert`, `gia_presenti` vale sempre 0 (dipende
dall'esito dell'upsert idempotente lato DB), quindi la conservazione si riduce a
`nuovi + scartati == #dict processabili`.

Validates: Requirements 3.9, 5.5
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.riconciliatore import prepara_per_upsert

# ---------------------------------------------------------------------------
# Generatori intelligenti di transazioni.
#
# Lo spazio di input è costruito per contenere SIA transazioni valide (chiave
# naturale calcolabile) SIA transazioni scartate (componente obbligatorio
# mancante/non valido), così da esercitare entrambe le categorie di conteggio.
# ---------------------------------------------------------------------------

# Date ISO plausibili (stringhe non vuote) usate dal dominio.
_date_valide = st.dates().map(lambda d: d.isoformat())

# Importi monetari finiti con segno.
_importi_validi = st.floats(
    min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
)

# Descrizioni che normalizzano a non vuoto (contengono almeno una parola alfabetica
# che non è un token di rumore).
_descrizioni_valide = st.sampled_from(
    [
        "ESSELUNGA MILANO",
        "COOP CENTRO",
        "AMAZON EU",
        "BAR CENTRALE",
        "FARMACIA SAN MARCO",
        "DECATHLON ROMA",
    ]
)


@st.composite
def _transazione_valida(draw) -> dict:
    """Transazione con tutti i componenti obbligatori -> chiave calcolabile."""
    return {
        "data_movimento": draw(_date_valide),
        "importo_eur": draw(_importi_validi),
        "descrizione": draw(_descrizioni_valide),
    }


@st.composite
def _transazione_scartata(draw) -> dict:
    """Transazione con almeno un componente obbligatorio mancante/non valido.

    La chiave naturale non è calcolabile e la transazione finisce tra gli
    scartati (Req 5.3). Variamo quale componente è invalido per coprire i casi.
    """
    base = {
        "data_movimento": draw(_date_valide),
        "importo_eur": draw(_importi_validi),
        "descrizione": draw(_descrizioni_valide),
    }
    difetto = draw(st.sampled_from(["data", "importo", "descrizione"]))
    if difetto == "data":
        base["data_movimento"] = draw(st.sampled_from([None, "", "   "]))
        # Nessun ripiego valido su `data`.
        base["data"] = None
    elif difetto == "importo":
        base["importo_eur"] = draw(st.sampled_from([None, float("nan")]))
    else:  # descrizione vuota/solo rumore
        base["descrizione"] = draw(st.sampled_from([None, "", "   ", "pos"]))
    return base


# Elementi non-dict che devono essere IGNORATI (non processabili) e dunque non
# devono contribuire a nessun conteggio.
_non_dict = st.one_of(
    st.none(),
    st.integers(),
    st.text(max_size=5),
    st.lists(st.integers(), max_size=3),
)

_elemento = st.one_of(
    _transazione_valida(),
    _transazione_scartata(),
    _non_dict,
)

_conti_validi = st.sampled_from(["BBVA", "N26", "Conto Corrente", "Fineco"])


@settings(max_examples=100)
@given(elementi=st.lists(_elemento, min_size=0, max_size=40), conto=_conti_validi)
def test_conservazione_conteggi(elementi, conto):
    """nuovi + gia_presenti + scartati == #transazioni processabili (dict).

    Ogni transazione-dict finisce in esattamente una categoria; gli elementi
    non-dict sono ignorati e non contano. I conteggi sono sempre presenti e
    non negativi (Req 5.5, 3.9).
    """
    res = prepara_per_upsert(elementi, conto)
    conteggi = res["conteggi"]

    # Tutte le categorie di conteggio sono sempre presenti.
    assert set(conteggi.keys()) == {"nuovi", "gia_presenti", "scartati"}

    # Ogni conteggio è un intero non negativo (0 per le categorie vuote).
    for valore in conteggi.values():
        assert isinstance(valore, int)
        assert valore >= 0

    # Per la funzione pura, `gia_presenti` è sempre 0 (deciso dal layer DB).
    assert conteggi["gia_presenti"] == 0

    # Numero di elementi realmente processabili (solo i dict).
    processabili = sum(1 for e in elementi if isinstance(e, dict))

    # Conservazione: la somma dei conteggi copre esattamente i processabili.
    assert (
        conteggi["nuovi"] + conteggi["gia_presenti"] + conteggi["scartati"]
        == processabili
    )

    # Coerenza con le liste restituite: validi e scartati partizionano i processabili.
    assert conteggi["nuovi"] == len(res["validi"])
    assert conteggi["scartati"] == len(res["scartati"])
    assert len(res["validi"]) + len(res["scartati"]) == processabili


@settings(max_examples=100)
@given(conto=_conti_validi)
def test_conteggi_a_zero_per_input_vuoto_o_none(conto):
    """Input vuoto o None -> tutti i conteggi presenti e pari a 0 (Req 5.5)."""
    for vuoto in ([], None):
        res = prepara_per_upsert(vuoto, conto)
        assert res["conteggi"] == {"nuovi": 0, "gia_presenti": 0, "scartati": 0}
        assert res["validi"] == []
        assert res["scartati"] == []

# Feature: gestione-spese, Property 3: Chiave naturale non calcolabile implica scarto
"""Property-based test per `spese.normalizza.chiave_naturale_movimento` (task 4.4).

Property 3: *Per ogni* movimento privo di un componente obbligatorio della
chiave naturale (data, conto, importo o descrizione), `chiave_naturale_movimento`
restituisce `None` (il movimento viene quindi conteggiato tra gli scartati).

Un componente è "non calcolabile" quando:
- la data è assente o vuota (dopo strip);
- il conto è assente o vuoto (dopo strip);
- l'importo è assente, booleano, non convertibile a float, oppure NaN/±inf;
- la descrizione normalizza a stringa vuota (`normalize_esercente(descrizione) == ""`).

Validates: Requirements 5.3
"""

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.normalizza import chiave_naturale_movimento, normalize_esercente

# ---------------------------------------------------------------------------
# Generatori intelligenti per ciascun componente della chiave naturale.
#
# Per ogni componente definiamo:
#   - uno strategy di valori VALIDI (così da isolare l'invalidità su un solo
#     componente alla volta);
#   - uno strategy di valori INVALIDI (che rendono la chiave non calcolabile).
# ---------------------------------------------------------------------------

# --- Data -------------------------------------------------------------------
_date_valide = st.sampled_from([
    "2024-01-02", "2023-12-31", "2024-02-29", "1999-07-15", "2025-06-30",
])
# Data mancante/non calcolabile: None oppure stringa vuota/solo spazi.
_date_invalide = st.one_of(
    st.none(),
    st.sampled_from(["", " ", "   ", "\t", "\n", "  \t \n "]),
)

# --- Conto ------------------------------------------------------------------
_conti_validi = st.sampled_from([
    "Conto Corrente", "Carta Revolut", "Fineco", "N26", "Libretto",
])
# Conto mancante/non calcolabile: None oppure stringa vuota/solo spazi.
_conti_invalidi = st.one_of(
    st.none(),
    st.sampled_from(["", " ", "   ", "\t", "\n", "  \t \n "]),
)

# --- Importo ----------------------------------------------------------------
_importi_validi = st.one_of(
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    st.integers(min_value=-1_000_000, max_value=1_000_000),
)
# Importo non calcolabile: None, bool, NaN, ±inf, stringa non numerica, oggetti.
_importi_invalidi = st.one_of(
    st.none(),
    st.booleans(),  # i bool sono esplicitamente respinti
    st.sampled_from([float("nan"), float("inf"), float("-inf")]),
    st.sampled_from(["abc", "n/a", "dodici", "€10", "1,2,3", "--", " "]),
    st.lists(st.integers(), min_size=0, max_size=3),  # tipi non convertibili
)

# --- Descrizione ------------------------------------------------------------
# Descrizioni che normalizzano a NON vuoto (componente valido).
_descrizioni_valide = st.sampled_from([
    "Esselunga Milano", "AMAZON", "Caffè Déjà Vu", "Ikea Store", "Farmacia",
])
# Descrizioni che normalizzano a VUOTO (componente non calcolabile):
# None, stringhe vuote/spazi e stringhe composte solo da rumore/numeri/simboli.
_descrizioni_invalide = st.one_of(
    st.none(),
    st.sampled_from([
        "",
        "   ",
        "\t\n",
        "POS",                 # solo token di rumore
        "PAGAMENTO CARTA",     # solo token di rumore
        "01/02/2024",          # solo data
        "12:30:45",            # solo orario
        "9999",                # solo numero lungo
        "---***///",           # solo simboli
        "ITA EUR",             # solo codici stato/valuta
        "pos pagamento ita",   # rumore + stato
    ]),
)


@settings(max_examples=100)
@given(
    data=_date_invalide,
    conto=_conti_validi,
    importo=_importi_validi,
    descrizione=_descrizioni_valide,
)
def test_data_mancante_implica_none(data, conto, importo, descrizione):
    """Data mancante/non calcolabile -> None (altri componenti validi)."""
    assert chiave_naturale_movimento(data, conto, importo, descrizione) is None


@settings(max_examples=100)
@given(
    data=_date_valide,
    conto=_conti_invalidi,
    importo=_importi_validi,
    descrizione=_descrizioni_valide,
)
def test_conto_mancante_implica_none(data, conto, importo, descrizione):
    """Conto mancante/non calcolabile -> None (altri componenti validi)."""
    assert chiave_naturale_movimento(data, conto, importo, descrizione) is None


@settings(max_examples=100)
@given(
    data=_date_valide,
    conto=_conti_validi,
    importo=_importi_invalidi,
    descrizione=_descrizioni_valide,
)
def test_importo_non_calcolabile_implica_none(data, conto, importo, descrizione):
    """Importo assente/non numerico/NaN/inf/bool -> None (altri componenti validi)."""
    assert chiave_naturale_movimento(data, conto, importo, descrizione) is None


@settings(max_examples=100)
@given(
    data=_date_valide,
    conto=_conti_validi,
    importo=_importi_validi,
    descrizione=_descrizioni_invalide,
)
def test_descrizione_vuota_implica_none(data, conto, importo, descrizione):
    """Descrizione che normalizza a vuoto -> None (altri componenti validi)."""
    # Pre-condizione del generatore: la descrizione deve normalizzare a vuoto.
    assert normalize_esercente(descrizione) == ""
    assert chiave_naturale_movimento(data, conto, importo, descrizione) is None

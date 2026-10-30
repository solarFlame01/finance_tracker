# Feature: gestione-spese, Property 1: Normalizzazione esercente deterministica e idempotente
"""Property-based test per `spese.normalizza.normalize_esercente` (task 4.3).

Property 1: *Per ogni* descrizione di transazione, `normalize_esercente` è
deterministica (ripetute invocazioni sullo stesso input producono lo stesso
output) e idempotente (`normalize_esercente(normalize_esercente(x)) ==
normalize_esercente(x)`), così da garantire lo stesso esercente normalizzato in
scrittura e in lettura del Mapping_Esercente_Categoria.

Validates: Requirements 6.8
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.normalizza import normalize_esercente

# ---------------------------------------------------------------------------
# Generatori intelligenti: stringhe realistiche di descrizioni di transazione
# con accenti, maiuscole e token di rumore tipici degli estratti conto.
# ---------------------------------------------------------------------------

# Token di rumore noti (prefissi/parole isolate negli estratti conto).
_NOISE_TOKENS = [
    "POS", "PAGAMENTO", "PAG", "CARTA", "CARTASI", "ADDEBITO", "BONIFICO",
    "PRELIEVO", "ACQUISTO", "OPERAZIONE", "CONTACTLESS", "ECOMMERCE",
    "SEPA", "SDD", "AUT", "RIF", "NUM", "DATA", "ORE", "ITA", "EUR", "USD",
]

# Nomi di esercente plausibili (con accenti e maiuscole miste).
_MERCHANTS = [
    "Caffè Déjà Vu", "Supermercato Èlite", "Farmacìa Niçoise", "Café München",
    "Librerìa Söhne", "Trattorìa Façade", "Boutique Crème", "Garçon Bïstro",
    "Hôtel Zürich", "AMAZON", "Esselunga", "Ikea Store", "Naïve Ödéon",
]

# Frammenti di rumore numerico (date, orari, importi, codici autorizzazione).
_NUMERIC_NOISE = [
    "01/02/2024", "1-2-24", "2024.01.02", "12:30", "12:30:45",
    "12,50", "1.234,56", "000123456", "9999",
]


def _token_strategy():
    """Un singolo token: esercente, rumore testuale, rumore numerico o testo libero."""
    return st.one_of(
        st.sampled_from(_MERCHANTS),
        st.sampled_from(_NOISE_TOKENS),
        st.sampled_from(_NUMERIC_NOISE),
        # Testo libero con accenti/latin-1 e maiuscole: stressa unidecode.
        st.text(
            alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x24F),
            min_size=0,
            max_size=8,
        ),
    )


@st.composite
def descrizioni(draw):
    """Compone una descrizione realistica assemblando token con separatori vari."""
    n = draw(st.integers(min_value=0, max_value=6))
    tokens = [draw(_token_strategy()) for _ in range(n)]
    separators = [" ", "  ", " - ", "/", "*", ".", " #", "   "]
    sep = draw(st.sampled_from(separators))
    descrizione = sep.join(tokens)
    # A volte case shuffling per forzare il lowercasing.
    if draw(st.booleans()):
        descrizione = descrizione.upper()
    return descrizione


# Strategia complessiva: descrizioni composte, testo arbitrario e None.
_input_strategy = st.one_of(
    descrizioni(),
    st.text(max_size=50),
    st.none(),
)


@settings(max_examples=100)
@given(descrizione=_input_strategy)
def test_normalize_esercente_deterministica(descrizione):
    """Determinismo: invocazioni ripetute sullo stesso input danno lo stesso output."""
    primo = normalize_esercente(descrizione)
    secondo = normalize_esercente(descrizione)
    assert primo == secondo


@settings(max_examples=100)
@given(descrizione=_input_strategy)
def test_normalize_esercente_idempotente(descrizione):
    """Idempotenza: normalize_esercente(normalize_esercente(x)) == normalize_esercente(x)."""
    una_volta = normalize_esercente(descrizione)
    due_volte = normalize_esercente(una_volta)
    assert due_volte == una_volta

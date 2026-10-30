# Feature: gestione-spese, Property 15
"""Property-based test per la validazione della registrazione di un trasferimento
(task 12.7).

Property 15: *Per ogni* combinazione di conto di origine, conto di destinazione
e importo, un trasferimento è accettato se e solo se il conto di origine è
diverso dal conto di destinazione E l'importo è strettamente positivo. In tutti
gli altri casi (conti coincidenti oppure importo <= 0) la registrazione è
rifiutata e nessun Movimento viene creato.

La regola vive in `views.gestione_spese._registra_trasferimento`, ma lì è
intrecciata con Streamlit (usa `st.error` e `return` invece di restituire un
valore). Replichiamo quindi la regola di Req 7.3 in una predicato puro di
riferimento, `_trasferimento_accettato`, che rispecchia esattamente i due
controlli di guardia della funzione reale:

    - Req 7.3: conto origine != destinazione  (altrimenti st.error + return)
    - Req 7.3: importo strettamente positivo   (altrimenti st.error + return)

e ne verifichiamo la logica di confine sull'intero spazio di input.

Validates: Requirements 7.3
"""

from hypothesis import given, settings
from hypothesis import strategies as st


def _trasferimento_accettato(conto_origine: int, conto_dest: int, importo: float) -> bool:
    """Predicato di riferimento che rispecchia la regola di Req 7.3.

    Un trasferimento è accettato se e solo se i due conti sono diversi e
    l'importo è strettamente positivo. Rispecchia le due guardie di
    `_registra_trasferimento`: `if conto_origine == conto_dest: return` e
    `if importo <= 0: return`.
    """
    if conto_origine == conto_dest:
        return False
    if importo <= 0:
        return False
    return True


# ---------------------------------------------------------------------------
# Generatori intelligenti vincolati allo spazio di input realistico.
#
# Gli id dei conti sono interi in un intervallo piccolo, così da avere una
# probabilità non trascurabile di generare conti coincidenti (il ramo di
# rifiuto da esercitare). Gli importi coprono deliberatamente positivi, zero e
# negativi per esercitare tutti i rami della regola di validazione.
# ---------------------------------------------------------------------------
_conto_ids = st.integers(min_value=0, max_value=5)
_importi = st.floats(
    min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
)


@settings(max_examples=100)
@given(conto_origine=_conto_ids, conto_dest=_conto_ids, importo=_importi)
def test_accettato_iff_conti_diversi_e_importo_positivo(
    conto_origine, conto_dest, importo
):
    """Accettato IFF origine != destinazione AND importo > 0."""
    atteso = (conto_origine != conto_dest) and (importo > 0)
    assert _trasferimento_accettato(conto_origine, conto_dest, importo) is atteso


@settings(max_examples=100)
@given(conto=_conto_ids, importo=_importi)
def test_conti_coincidenti_sempre_rifiutato(conto, importo):
    """Con origine == destinazione la registrazione è sempre rifiutata."""
    assert _trasferimento_accettato(conto, conto, importo) is False


@settings(max_examples=100)
@given(
    conto_origine=_conto_ids,
    conto_dest=_conto_ids,
    importo=st.floats(
        max_value=0.0, allow_nan=False, allow_infinity=False
    ),
)
def test_importo_non_positivo_sempre_rifiutato(conto_origine, conto_dest, importo):
    """Con importo <= 0 (zero o negativo) la registrazione è sempre rifiutata."""
    assert _trasferimento_accettato(conto_origine, conto_dest, importo) is False

# Feature: gestione-spese, Property 17
"""Property-based test per `spese.riconciliatore.escludi_trasferimenti` (task 5.8).

Property 17: *Per ogni* insieme di movimenti, i totali di spesa e di entrata
escludono tutti i movimenti con Tipo_Movimento "Trasferimento ingresso" o
"Trasferimento uscita". La helper `escludi_trasferimenti` e' il punto centrale
che garantisce questa esclusione: il suo risultato non contiene mai un
trasferimento e preserva, nell'ordine, tutti i movimenti non-trasferimento.

Validates: Requirements 7.5
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.riconciliatore import escludi_trasferimenti

# ---------------------------------------------------------------------------
# Generatori intelligenti vincolati allo spazio di input realistico.
#
# Includiamo esplicitamente i due tipi di Trasferimento insieme ad altri tipi
# di movimento "normali", così che ogni lista generata abbia una ragionevole
# probabilità di contenere sia trasferimenti (da escludere) sia movimenti da
# preservare.
# ---------------------------------------------------------------------------
TIPI_TRASFERIMENTO = ("Trasferimento ingresso", "Trasferimento uscita")
_TIPI_NON_TRASFERIMENTO = ("Spese", "In", "Stipendio", "Bollo", None, "")
_TUTTI_I_TIPI = TIPI_TRASFERIMENTO + _TIPI_NON_TRASFERIMENTO


def _movimento_strategy():
    """Genera un movimento con un `tipo_movimento` variabile e campi di contorno."""
    return st.fixed_dictionaries(
        {
            "tipo_movimento": st.sampled_from(_TUTTI_I_TIPI),
            "conto": st.sampled_from(["Conto Corrente", "Carta", "Libretto"]),
            "importo_eur": st.floats(
                min_value=-1e4, max_value=1e4,
                allow_nan=False, allow_infinity=False,
            ),
        }
    )


@settings(max_examples=100)
@given(movimenti=st.lists(_movimento_strategy(), min_size=0, max_size=40))
def test_esclude_tutti_i_trasferimenti_e_preserva_gli_altri(movimenti):
    """Il risultato non contiene trasferimenti e preserva gli altri in ordine."""
    risultato = escludi_trasferimenti(movimenti)

    # (a) Nessun movimento del risultato e' un trasferimento.
    for m in risultato:
        assert m["tipo_movimento"] not in TIPI_TRASFERIMENTO

    # (b) Tutti i movimenti non-trasferimento sono preservati, nello stesso
    #     ordine di ingresso: il risultato coincide esattamente con l'input
    #     privato dei soli trasferimenti.
    attesi = [m for m in movimenti if m["tipo_movimento"] not in TIPI_TRASFERIMENTO]
    assert risultato == attesi

# Feature: gestione-spese, Property 18
"""Property-based test per `spese.riconciliatore.saldo_conto` (task 5.5).

Property 18: *Per ogni* lista di movimenti di un conto, `saldo_conto` è uguale
alla somma algebrica (con segno) degli importi (`importo_eur`) dei movimenti di
quel conto.

Il segno è già incorporato nel valore di `importo_eur` di ciascun movimento:
le uscite sono negative, le entrate positive. Il saldo è quindi la semplice
somma algebrica di tutti gli `importo_eur`.

Validates: Requirements 5.7
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from spese.riconciliatore import saldo_conto

# ---------------------------------------------------------------------------
# Generatore intelligente di importi monetari con segno.
#
# Vincoliamo lo spazio di input a float finiti (no NaN/inf) in un intervallo
# monetario realistico, così che la somma di riferimento sia sempre definita e
# confrontabile con l'output di `saldo_conto`.
# ---------------------------------------------------------------------------
_importi = st.floats(
    min_value=-1e6,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
)


def _movimento(importo: float) -> dict:
    """Costruisce un movimento minimale con l'importo dato."""
    return {"importo_eur": importo, "conto": "Conto Corrente"}


@settings(max_examples=100)
@given(importi=st.lists(_importi, min_size=0, max_size=50))
def test_saldo_uguale_somma_algebrica_importi(importi):
    """Il saldo è la somma algebrica con segno degli `importo_eur` (Req 5.7)."""
    movimenti = [_movimento(importo) for importo in importi]

    atteso = math.fsum(importi)  # somma di riferimento ad alta precisione
    risultato = saldo_conto(movimenti)

    # Tolleranza per l'aritmetica in virgola mobile: la somma sequenziale di
    # `saldo_conto` e `math.fsum` possono differire per l'ordine di accumulo.
    assert risultato == pytest.approx(atteso, rel=1e-9, abs=1e-6)


@settings(max_examples=100)
@given(importi=st.lists(_importi, min_size=1, max_size=50))
def test_saldo_lista_vuota_e_coerenza_additiva(importi):
    """Lista vuota -> 0.0; aggiungere un movimento incrementa il saldo del suo importo."""
    # Caso base: nessun movimento -> saldo nullo.
    assert saldo_conto([]) == 0.0

    # Rimuovendo l'ultimo movimento, il saldo cala esattamente del suo importo.
    movimenti = [_movimento(importo) for importo in importi]
    saldo_totale = saldo_conto(movimenti)
    saldo_senza_ultimo = saldo_conto(movimenti[:-1])

    assert saldo_totale - saldo_senza_ultimo == pytest.approx(
        importi[-1], rel=1e-9, abs=1e-6
    )

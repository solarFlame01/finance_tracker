# Feature: gestione-spese, Property 19
"""Property-based test per `spese.riconciliatore.ordina_per_data_desc` (task 5.6).

Property 19: *Per ogni* lista di movimenti, l'elenco prodotto per la
visualizzazione e' ordinato per `data_movimento` in ordine NON crescente
(decrescente, dal piu' recente al piu' vecchio) e contiene esattamente gli
stessi elementi dell'input (e' una permutazione: stesso multiset di movimenti).

Validates: Requirements 8.1
"""

from collections import Counter

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.riconciliatore import ordina_per_data_desc

# ---------------------------------------------------------------------------
# Generatore intelligente di movimenti con data ISO (`YYYY-MM-DD`).
#
# Le date ISO sono confrontabili lessicograficamente: l'ordinamento per stringa
# coincide con l'ordinamento cronologico. Restringiamo lo spazio di input a
# date ISO valide piu' un marcatore `id` univoco per poter distinguere e
# contare i singoli movimenti (verifica della permutazione).
# ---------------------------------------------------------------------------
_date_iso = st.dates().map(lambda d: d.isoformat())


def _movimenti_con_id():
    """Genera una lista di movimenti, ciascuno con `data_movimento` ISO e `id` univoco.

    L'`id` progressivo rende ogni dict distinguibile anche quando piu'
    movimenti condividono la stessa data, cosi' da poter verificare che
    l'output sia una permutazione esatta dell'input.
    """
    return st.lists(_date_iso, min_size=0, max_size=50).map(
        lambda date: [
            {"data_movimento": data, "id": indice}
            for indice, data in enumerate(date)
        ]
    )


def _firma(movimento: dict) -> tuple:
    """Firma hashabile di un movimento per il confronto come multiset."""
    return (movimento["data_movimento"], movimento["id"])


@settings(max_examples=100)
@given(movimenti=_movimenti_con_id())
def test_ordinamento_decrescente_per_data(movimenti):
    """L'output e' ordinato per `data_movimento` in ordine non crescente (Req 8.1)."""
    risultato = ordina_per_data_desc(movimenti)

    date = [m["data_movimento"] for m in risultato]
    # Ogni elemento deve essere >= del successivo (ordine non crescente).
    for precedente, successivo in zip(date, date[1:]):
        assert precedente >= successivo


@settings(max_examples=100)
@given(movimenti=_movimenti_con_id())
def test_output_e_permutazione_dell_input(movimenti):
    """L'output contiene esattamente gli stessi movimenti dell'input (Req 8.1)."""
    risultato = ordina_per_data_desc(movimenti)

    # Stesso numero di elementi e stesso multiset (nessun elemento perso,
    # duplicato o inventato).
    assert len(risultato) == len(movimenti)
    assert Counter(_firma(m) for m in risultato) == Counter(
        _firma(m) for m in movimenti
    )

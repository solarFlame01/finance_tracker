# Feature: gestione-spese, Property 20
"""Property-based test per `spese.riconciliatore.applica_filtri` (task 5.7).

Property 20: *Per ogni* lista di movimenti e *per ogni* combinazione di filtri
(conto, categoria, intervallo di date con estremi inclusi), l'insieme filtrato
contiene esattamente i movimenti che soddisfano tutti i filtri attivi: nessun
movimento conforme viene omesso e nessun movimento non conforme viene incluso.

Un filtro `None` è inattivo e non restringe i risultati. L'intervallo di date
ha estremi inclusi e le date sono confrontate in formato ISO (`YYYY-MM-DD`),
lessicograficamente ordinabile.

Validates: Requirements 8.3, 8.4, 8.5
"""

from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.riconciliatore import applica_filtri

# ---------------------------------------------------------------------------
# Generatori intelligenti vincolati allo spazio di input realistico.
#
# Usiamo piccoli domini finiti per conti, categorie e date così che i filtri
# generati abbiano una ragionevole probabilità di selezionare sottoinsiemi non
# banali (e non solo l'insieme vuoto o quello totale).
# ---------------------------------------------------------------------------
_CONTI = ["Conto Corrente", "Carta", "Libretto"]
_CATEGORIE = ["Spesa", "Casa", "Svago", "Stipendio"]
_DATE = [date(2024, 1, 1).isoformat(),
         date(2024, 3, 15).isoformat(),
         date(2024, 6, 30).isoformat(),
         date(2024, 9, 10).isoformat(),
         date(2024, 12, 31).isoformat()]


def _movimento_strategy():
    """Genera un movimento con i campi rilevanti per i filtri."""
    return st.fixed_dictionaries(
        {
            "conto": st.sampled_from(_CONTI),
            "categoria": st.sampled_from(_CATEGORIE),
            "data_movimento": st.sampled_from(_DATE),
            # Campo extra ininfluente sui filtri, per realismo.
            "importo_eur": st.floats(
                min_value=-1e4, max_value=1e4,
                allow_nan=False, allow_infinity=False,
            ),
        }
    )


# Filtri: ciascun parametro può essere None (inattivo) o un valore dal dominio.
_filtro_conto = st.one_of(st.none(), st.sampled_from(_CONTI))
_filtro_categoria = st.one_of(st.none(), st.sampled_from(_CATEGORIE))
_filtro_data = st.one_of(st.none(), st.sampled_from(_DATE))


def _soddisfa_filtri(movimento, conto, categoria, data_da, data_a):
    """Predicato di riferimento, indipendente dall'implementazione sotto test."""
    if conto is not None and movimento["conto"] != conto:
        return False
    if categoria is not None and movimento["categoria"] != categoria:
        return False
    if data_da is not None and movimento["data_movimento"] < data_da:
        return False
    if data_a is not None and movimento["data_movimento"] > data_a:
        return False
    return True


@settings(max_examples=100)
@given(
    movimenti=st.lists(_movimento_strategy(), min_size=0, max_size=40),
    conto=_filtro_conto,
    categoria=_filtro_categoria,
    data_da=_filtro_data,
    data_a=_filtro_data,
)
def test_filtri_selezionano_esattamente_i_conformi(
    movimenti, conto, categoria, data_da, data_a
):
    """Il risultato contiene esattamente i movimenti conformi a tutti i filtri attivi."""
    risultato = applica_filtri(
        movimenti, conto=conto, categoria=categoria, data_da=data_da, data_a=data_a
    )

    attesi = [
        m for m in movimenti
        if _soddisfa_filtri(m, conto, categoria, data_da, data_a)
    ]

    # (a) Nessun movimento conforme omesso E nessun non conforme incluso:
    #     il risultato coincide esattamente (ordine compreso) con gli attesi.
    assert risultato == attesi

    # (b) Soundness: ogni movimento restituito soddisfa tutti i filtri attivi.
    for m in risultato:
        assert _soddisfa_filtri(m, conto, categoria, data_da, data_a)

    # (c) Completeness: nessun movimento conforme è escluso dal risultato.
    for m in movimenti:
        if _soddisfa_filtri(m, conto, categoria, data_da, data_a):
            assert m in risultato


@settings(max_examples=100)
@given(movimenti=st.lists(_movimento_strategy(), min_size=0, max_size=40))
def test_filtri_tutti_none_restituiscono_tutto(movimenti):
    """Con tutti i filtri inattivi (None) il risultato coincide con l'input."""
    assert applica_filtri(movimenti) == movimenti


@settings(max_examples=100)
@given(
    movimenti=st.lists(_movimento_strategy(), min_size=1, max_size=40),
    data=st.sampled_from(_DATE),
)
def test_intervallo_date_ha_estremi_inclusi(movimenti, data):
    """Un movimento con data uguale a data_da o data_a non viene mai escluso (Req 8.5)."""
    # data_da == data_a == data: devono restare solo i movimenti con quella data.
    risultato = applica_filtri(movimenti, data_da=data, data_a=data)
    attesi = [m for m in movimenti if m["data_movimento"] == data]
    assert risultato == attesi

# Feature: gestione-spese, Property 16
"""Property-based test per `spese.riconciliatore.rileva_coppie_trasferimento` (task 5.9).

Property 16: *Per ogni* insieme di movimenti, `rileva_coppie_trasferimento`
restituisce esattamente le coppie costituite da un'uscita su un conto e da
un'entrata su un conto diverso con differenza di importo pari a 0 e differenza
di data pari a 0 giorni, e nessuna coppia che non soddisfi tali criteri.

In altre parole, l'insieme delle coppie restituite deve coincidere esattamente
con l'insieme delle coppie valide: nessuna coppia non valida è inclusa e
nessuna coppia valida viene mancata.

Validates: Requirements 7.4
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.riconciliatore import (
    TIPO_ENTRATA,
    TIPO_USCITA,
    rileva_coppie_trasferimento,
)

# ---------------------------------------------------------------------------
# Generatori intelligenti vincolati allo spazio di input rilevante.
#
# - tipo_movimento: generiamo soprattutto 'Spese'/'In' (i soli candidati), ma
#   includiamo anche un tipo non candidato per verificare che venga escluso.
# - conto: un piccolo alfabeto di nomi così da avere con buona probabilità sia
#   coppie sullo stesso conto (da escludere) sia su conti diversi.
# - data_movimento: poche date ISO per favorire collisioni di data.
# - importo_eur: importi monetari finiti; per aumentare i match generiamo
#   grandezze da un piccolo insieme e assegniamo il segno coerente col tipo.
# ---------------------------------------------------------------------------

_tipi = st.sampled_from([TIPO_USCITA, TIPO_ENTRATA, "Trasferimento ingresso"])
_conti = st.sampled_from(["A", "B", "C"])
_date = st.sampled_from(["2024-01-10", "2024-01-11", "2024-02-01"])
_grandezze = st.sampled_from([0.0, 10.0, 99.99, 100.0, 250.5])


@st.composite
def _movimento(draw):
    tipo = draw(_tipi)
    grandezza = draw(_grandezze)
    # Segno coerente col dominio: le uscite ('Spese') sono negative, le entrate
    # ('In') positive. Per i tipi non candidati il segno è irrilevante.
    if tipo == TIPO_USCITA:
        importo = -grandezza
    elif tipo == TIPO_ENTRATA:
        importo = grandezza
    else:
        importo = draw(st.sampled_from([-grandezza, grandezza]))
    return {
        "tipo_movimento": tipo,
        "conto": draw(_conti),
        "data_movimento": draw(_date),
        "importo_eur": importo,
    }


def _coppie_attese(movimenti):
    """Oracolo indipendente: calcola l'insieme delle coppie valide per indice.

    Replica i criteri di Property 16 senza riusare la logica di produzione,
    identificando le coppie tramite gli indici posizionali (uniche a prescindere
    da movimenti con contenuto identico)."""
    uscite = []
    entrate = []
    for idx, mov in enumerate(movimenti):
        tipo = mov["tipo_movimento"]
        conto = mov["conto"]
        data = str(mov["data_movimento"])
        grandezza = round(abs(float(mov["importo_eur"])), 2)
        if tipo == TIPO_USCITA:
            uscite.append((idx, conto, data, grandezza))
        elif tipo == TIPO_ENTRATA:
            entrate.append((idx, conto, data, grandezza))

    attese = set()
    for iu, conto_u, data_u, grand_u in uscite:
        for ie, conto_e, data_e, grand_e in entrate:
            if conto_u != conto_e and data_u == data_e and grand_u == grand_e:
                attese.add((iu, ie))
    return attese


@settings(max_examples=100)
@given(movimenti=st.lists(_movimento(), min_size=0, max_size=12))
def test_coppie_esattamente_quelle_valide(movimenti):
    """Le coppie restituite coincidono esattamente con quelle valide (Req 7.4)."""
    risultato = rileva_coppie_trasferimento(movimenti)

    # Traduci il risultato (coppie di dict) in coppie di indici per confronto
    # insiemistico robusto anche in presenza di movimenti con contenuto uguale.
    ids = {id(mov): idx for idx, mov in enumerate(movimenti)}
    coppie_ottenute = {(ids[id(u)], ids[id(e)]) for u, e in risultato}

    coppie_attese = _coppie_attese(movimenti)

    # Esattezza: nessuna coppia non valida inclusa, nessuna coppia valida mancata.
    assert coppie_ottenute == coppie_attese


@settings(max_examples=100)
@given(movimenti=st.lists(_movimento(), min_size=0, max_size=12))
def test_ogni_coppia_rispetta_i_criteri(movimenti):
    """Ogni coppia restituita soddisfa tutti i criteri: tipo, conto diverso, data e importo."""
    for uscita, entrata in rileva_coppie_trasferimento(movimenti):
        assert uscita["tipo_movimento"] == TIPO_USCITA
        assert entrata["tipo_movimento"] == TIPO_ENTRATA
        assert uscita["conto"] != entrata["conto"]
        assert str(uscita["data_movimento"]) == str(entrata["data_movimento"])
        assert round(abs(float(uscita["importo_eur"])), 2) == round(
            abs(float(entrata["importo_eur"])), 2
        )

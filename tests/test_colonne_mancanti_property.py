# Feature: gestione-spese, Property 6: Rilevamento delle colonne mancanti
"""Property-based test per `spese.excel_importer.leggi_storico_excel` (task 7.5).

Property 6: *Per ogni* sottoinsieme di colonne attese rimosso dal file,
l'insieme di colonne segnalate come mancanti dall'Importatore_Excel è
esattamente uguale all'insieme delle colonne rimosse.

Strategia: si sintetizza in memoria un `.xlsx` (DataFrame -> BytesIO, engine
`openpyxl`) contenente solo le colonne attese NON rimosse. Si verifica poi che
`leggi_storico_excel` segnali come `colonne_mancanti` esattamente l'insieme
delle colonne rimosse (indipendentemente dall'ordine).

Validates: Requirements 3.3
"""

import io

import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from spese.excel_importer import COLONNE_ATTESE, leggi_storico_excel


def _costruisci_xlsx(colonne: list[str]) -> io.BytesIO:
    """Crea in memoria un `.xlsx` con le colonne indicate e poche righe.

    Il contenuto delle celle è irrilevante per la proprietà sotto esame (che
    riguarda solo i NOMI delle colonne presenti/assenti): si inseriscono alcune
    righe di valori di esempio per avere un foglio non banale.
    """
    # Due righe di dati fittizi per ciascuna colonna presente.
    dati = {c: [f"{c}_0", f"{c}_1"] for c in colonne}
    df = pd.DataFrame(dati, columns=colonne)

    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    return buffer


# Sottoinsieme (anche vuoto, anche totale) delle colonne attese da RIMUOVERE.
# `st.lists(..., unique=True)` su un dominio campionato genera un sottoinsieme
# ordinato senza ripetizioni; lo normalizziamo a `set` per il confronto.
_sottoinsiemi_da_rimuovere = st.lists(
    st.sampled_from(COLONNE_ATTESE),
    unique=True,
    max_size=len(COLONNE_ATTESE),
).map(set)


# `max_examples=100`: lo spazio dei sottoinsiemi è piccolo (2^9), ma l'IO xlsx
# è il collo di bottiglia; 100 esempi restano rapidi e coprono bene il dominio.
# `deadline=None`: la scrittura/lettura di un `.xlsx` ha tempi variabili (il
# primo esempio paga l'inizializzazione di openpyxl), quindi disattiviamo la
# deadline per-esempio per evitare falsi fallimenti da timing non deterministico.
@settings(max_examples=100, deadline=None)
@given(rimosse=_sottoinsiemi_da_rimuovere)
def test_colonne_mancanti_uguali_alle_rimosse(rimosse):
    """Le colonne segnalate mancanti coincidono con quelle rimosse dal file."""
    colonne_presenti = [c for c in COLONNE_ATTESE if c not in rimosse]
    buffer = _costruisci_xlsx(colonne_presenti)

    righe_mappate, colonne_mancanti = leggi_storico_excel(buffer)

    # L'insieme segnalato è ESATTAMENTE quello rimosso (ordine irrilevante).
    assert set(colonne_mancanti) == set(rimosse)

    # Nessun duplicato tra le colonne segnalate mancanti.
    assert len(colonne_mancanti) == len(set(colonne_mancanti))

    # Coerenza del contratto: se mancano colonne, non si mappa alcuna riga;
    # se non ne mancano, tutte le colonne attese sono presenti (Req 3.3, 3.1).
    if rimosse:
        assert righe_mappate == []
    else:
        assert colonne_mancanti == []
        assert len(righe_mappate) == 2

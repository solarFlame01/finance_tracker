# Feature: gestione-spese, Property 2: Dedup idempotente sulla Chiave_Naturale_Movimento
"""Property-based test per la deduplicazione idempotente sulla chiave naturale
(task 10.5).

Property 2: *Per ogni* insieme di movimenti, applicare la deduplicazione sulla
Chiave_Naturale_Movimento è idempotente:

1. ripetere il salvataggio degli stessi movimenti NON altera l'insieme
   risultante (la cardinalità resta invariata);
2. i movimenti con chiave naturale già presente CONSERVANO i valori esistenti
   (nessun aggiornamento: `ignore_duplicates=True`);
3. l'unione di un insieme con un suo sovra-insieme sovrapposto NON crea
   duplicati.

L'idempotenza è garantita, nel sistema reale, dall'UPSERT su Supabase con
`on_conflict` sulla Chiave_Naturale_Movimento e `ignore_duplicates=True`
(vedi `database.upsert_movimenti`). Qui la semantica dell'UPSERT viene
modellata da uno store in memoria auto-contenuto (`StoreMovimenti`), un dict
keyato sulla chiave naturale calcolata con
`spese.normalizza.chiave_naturale_movimento`. Nessuna rete né Supabase reale
sono coinvolti.

La chiave di conflitto replica quella reale:
``(data_movimento, conto_id, importo_eur, descrizione_normalizzata)``
derivata da `chiave_naturale_movimento(data, conto, importo_eur, descrizione)`.

Validates: Requirements 3.7, 3.8, 5.1, 5.2, 5.4
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.normalizza import chiave_naturale_movimento


# ---------------------------------------------------------------------------
# Store in memoria che mima l'UPSERT con ignore_duplicates=True sulla chiave
# naturale (replica la semantica di database.upsert_movimenti senza Supabase).
# ---------------------------------------------------------------------------
class StoreMovimenti:
    """Dizionario keyato sulla Chiave_Naturale_Movimento.

    `upsert` applica la semantica `ignore_duplicates=True`: la prima volta che
    una chiave compare il record viene inserito; le occorrenze successive della
    stessa chiave vengono ignorate (il record esistente resta immutato). I
    movimenti la cui chiave naturale non è calcolabile (`None`) sono scartati e
    non entrano nello store (coerente con Req 5.3 e con `prepara_per_upsert`).
    """

    def __init__(self):
        self._per_chiave = {}

    def upsert(self, movimenti):
        """Inserisce i movimenti ignorando i duplicati sulla chiave naturale.

        Ritorna il numero di record EFFETTIVAMENTE inseriti in questa chiamata
        (le chiavi già presenti e quelle non calcolabili non contano).
        """
        inseriti = 0
        for mov in movimenti:
            chiave = _chiave_di(mov)
            if chiave is None:
                continue  # chiave non calcolabile -> scartato
            if chiave not in self._per_chiave:
                self._per_chiave[chiave] = dict(mov)
                inseriti += 1
            # else: duplicato -> ignorato, valore esistente invariato
        return inseriti

    @property
    def chiavi(self):
        return set(self._per_chiave.keys())

    def __len__(self):
        return len(self._per_chiave)

    def record(self, chiave):
        return self._per_chiave.get(chiave)


def _chiave_di(mov: dict):
    """Calcola la Chiave_Naturale_Movimento di un record movimento."""
    return chiave_naturale_movimento(
        mov.get("data_movimento"),
        mov.get("conto"),
        mov.get("importo_eur"),
        mov.get("descrizione"),
    )


# ---------------------------------------------------------------------------
# Generatori: movimenti con chiave naturale CALCOLABILE, con componenti scelti
# da piccoli pool così da forzare chiavi ripetute e sovrapposte tra liste.
# ---------------------------------------------------------------------------
_date = st.sampled_from([
    "2024-01-02", "2023-12-31", "2024-02-29", "1999-07-15", "2025-06-30",
])
_conti = st.sampled_from(["Conto Corrente", "Revolut", "Fineco", "N26"])
_importi = st.sampled_from([10.0, -42.5, 100.0, -7.99, 0.0, 1234.56])
# Descrizioni che normalizzano a NON vuoto (chiave calcolabile garantita).
_descrizioni = st.sampled_from([
    "Esselunga Milano", "AMAZON", "Ikea Store", "Farmacia", "Caffè Déjà Vu",
])


@st.composite
def _movimento(draw):
    """Un record movimento con chiave naturale sempre calcolabile.

    `nota` è un campo NON appartenente alla chiave: serve a verificare che i
    duplicati conservino il valore del PRIMO inserito (ignore_duplicates).
    """
    return {
        "data_movimento": draw(_date),
        "conto": draw(_conti),
        "importo_eur": draw(_importi),
        "descrizione": draw(_descrizioni),
        "nota": draw(st.text(min_size=0, max_size=8)),
    }


_movimenti = st.lists(_movimento(), min_size=0, max_size=30)


# ---------------------------------------------------------------------------
# Property 2.1 - Idempotenza: riapplicare gli stessi movimenti non cambia la
# cardinalità dell'insieme risultante.
# ---------------------------------------------------------------------------
@settings(max_examples=100)
@given(movimenti=_movimenti)
def test_riapplicazione_non_cambia_cardinalita(movimenti):
    """Salvare due volte lo stesso insieme -> cardinalità invariata."""
    store = StoreMovimenti()

    store.upsert(movimenti)
    cardinalita_dopo_prima = len(store)

    # La seconda applicazione non deve inserire nulla di nuovo.
    inseriti_seconda = store.upsert(movimenti)
    assert inseriti_seconda == 0
    assert len(store) == cardinalita_dopo_prima

    # La cardinalità è esattamente il numero di chiavi naturali distinte.
    chiavi_distinte = {
        k for k in (_chiave_di(m) for m in movimenti) if k is not None
    }
    assert store.chiavi == chiavi_distinte
    assert len(store) == len(chiavi_distinte)


# ---------------------------------------------------------------------------
# Property 2.2 - I movimenti con chiave già presente conservano i valori
# esistenti (ignore_duplicates: nessun overwrite dei campi non-chiave).
# ---------------------------------------------------------------------------
@settings(max_examples=100)
@given(base=_movimenti, modifiche=_movimenti)
def test_duplicati_conservano_i_valori_esistenti(base, modifiche):
    """Re-upsert con stessa chiave ma `nota` diversa -> resta il primo valore."""
    store = StoreMovimenti()
    store.upsert(base)

    # Snapshot dei record presenti dopo il primo inserimento.
    snapshot = {k: dict(store.record(k)) for k in store.chiavi}

    # Prepara una seconda passata che, per le chiavi già presenti, usa un
    # record con `nota` deliberatamente alterata.
    seconda_passata = []
    for mov in modifiche:
        chiave = _chiave_di(mov)
        if chiave in snapshot:
            mov = dict(mov)
            mov["nota"] = (mov.get("nota") or "") + "__MODIFICATO__"
        seconda_passata.append(mov)

    store.upsert(seconda_passata)

    # Ogni chiave già presente deve conservare ESATTAMENTE il record originale.
    for chiave, originale in snapshot.items():
        assert store.record(chiave) == originale


# ---------------------------------------------------------------------------
# Property 2.3 - L'unione con un sovra-insieme sovrapposto non crea duplicati:
# il risultato ha esattamente le chiavi naturali distinte dell'unione.
# ---------------------------------------------------------------------------
@settings(max_examples=100)
@given(parziale=_movimenti, extra=_movimenti)
def test_unione_sovrainsieme_non_crea_duplicati(parziale, extra):
    """upsert(A) poi upsert(A ∪ extra) -> chiavi == chiavi distinte di A ∪ extra."""
    superset = parziale + extra  # sovra-insieme che SOVRAPPONE 'parziale'

    store = StoreMovimenti()
    store.upsert(parziale)
    store.upsert(superset)

    chiavi_attese = {
        k for k in (_chiave_di(m) for m in superset) if k is not None
    }
    assert store.chiavi == chiavi_attese
    # Nessun duplicato: cardinalità == numero di chiavi distinte.
    assert len(store) == len(chiavi_attese)

    # Riapplicare ancora il superset è idempotente (nessun nuovo inserimento).
    assert store.upsert(superset) == 0
    assert len(store) == len(chiavi_attese)

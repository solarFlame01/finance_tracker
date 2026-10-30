# Feature: gestione-spese, Property 13: Esercente non mappato resta da categorizzare
"""Property-based test per `spese.categorizzatore.categorizza` (task 6.4).

Property 13: *Per ogni* Movimento il cui Esercente normalizzato NON è presente
nel Mapping_Esercente_Categoria fornito, `categorizza` lascia il Movimento
senza Categoria assegnata (`categoria` e `sotto_categoria` a `None`) e lo
contrassegna come da categorizzare (`da_categorizzare=True`).

Validates: Requirements 6.4
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.categorizzatore import categorizza
from spese.normalizza import normalize_esercente

# ---------------------------------------------------------------------------
# Generatori intelligenti.
#
# Il vincolo chiave della Property 13 è che l'esercente normalizzato del
# movimento NON deve essere presente nel mapping. `categorizza` calcola la
# chiave di lookup come `normalize_esercente(descrizione)`, quindi per
# garantire il "miss" costruiamo il mapping escludendo deliberatamente quella
# chiave: o un mapping vuoto, oppure voci le cui chiavi sono normalizzazioni di
# descrizioni diverse (e, per sicurezza, filtrate per non coincidere).
# ---------------------------------------------------------------------------

# Descrizioni plausibili che, normalizzate, producono un esercente non vuoto.
_DESCRIZIONI = [
    "Caffè Déjà Vu",
    "POS Supermercato Èlite 01/02/2024",
    "PAGAMENTO Amazon Marketplace",
    "Esselunga Milano ITA",
    "CARTA Librerìa Söhne 12:30",
    "Trattorìa Façade",
    "IKEA Store 1.234,56 EUR",
    "Hôtel Zürich",
    "Boutique Crème Paris FRA",
    "Garçon Bïstro",
]

_CATEGORIE = ["Spesa", "Casa", "Trasporti", "Svago", "Salute", "Bollette"]
_SOTTO_CATEGORIE = ["Alimentari", "Affitto", "Benzina", "Cinema", "Farmacia"]


@st.composite
def movimento_e_mapping_senza_esercente(draw):
    """Genera un movimento e un mapping che NON contiene il suo esercente.

    Il mapping è o vuoto o composto da voci la cui chiave è garantita diversa
    dall'esercente normalizzato del movimento: ogni chiave candidata viene
    inserita solo se, una volta normalizzata, differisce dalla chiave del
    movimento.
    """
    descrizione = draw(st.sampled_from(_DESCRIZIONI))
    esercente_norm = normalize_esercente(descrizione)

    # Costruisci un mapping di rumore con chiavi diverse dall'esercente target.
    mapping: dict[str, dict] = {}
    altre = draw(st.lists(st.sampled_from(_DESCRIZIONI), min_size=0, max_size=5))
    for d in altre:
        chiave = normalize_esercente(d)
        # Escludi deliberatamente la chiave del movimento (garantisce il miss).
        if chiave and chiave != esercente_norm:
            mapping[chiave] = {
                "categoria": draw(st.sampled_from(_CATEGORIE)),
                "sotto_categoria": draw(st.sampled_from(_SOTTO_CATEGORIE)),
            }

    # Il movimento può avere campi pregressi che devono essere sovrascritti a
    # None (categoria/sotto_categoria) per confermare il reset.
    movimento = {
        "descrizione": descrizione,
        "categoria": draw(st.one_of(st.none(), st.sampled_from(_CATEGORIE))),
        "sotto_categoria": draw(
            st.one_of(st.none(), st.sampled_from(_SOTTO_CATEGORIE))
        ),
        "da_categorizzare": draw(st.booleans()),
        "importo_eur": draw(
            st.floats(min_value=-5000, max_value=5000,
                      allow_nan=False, allow_infinity=False)
        ),
    }

    return movimento, mapping, esercente_norm


@settings(max_examples=100)
@given(dati=movimento_e_mapping_senza_esercente())
def test_categorizza_esercente_non_mappato(dati):
    """Esercente assente dal mapping => resta da categorizzare, senza categoria."""
    movimento, mapping, esercente_norm = dati

    risultato = categorizza(movimento, mapping)

    # Precondizione della property: l'esercente NON è nel mapping.
    assert esercente_norm not in mapping

    # L'esercente normalizzato è comunque calcolato e riportato.
    assert risultato["esercente_normalizzato"] == esercente_norm

    # Nessuna categoria/sotto-categoria assegnata.
    assert risultato["categoria"] is None
    assert risultato["sotto_categoria"] is None

    # Il movimento è contrassegnato come da categorizzare.
    assert risultato["da_categorizzare"] is True

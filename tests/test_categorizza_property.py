# Feature: gestione-spese, Property 12: Auto-categorizzazione da mapping corrente
"""Property-based test per `spese.categorizzatore.categorizza` (task 6.3).

Property 12: *Per ogni* movimento il cui esercente normalizzato è presente nel
Mapping_Esercente_Categoria fornito, `categorizza` assegna la Categoria di
default della voce e, quando la voce ha una Sotto_Categoria di default, assegna
anche quella; il flag `da_categorizzare` è `False`. Poiché la funzione usa il
mapping corrente passato in input, riflette sempre l'ultima correzione manuale.

Validates: Requirements 6.2, 6.3, 6.7
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.categorizzatore import categorizza
from spese.normalizza import normalize_esercente

# ---------------------------------------------------------------------------
# Generatori intelligenti.
#
# Il vincolo chiave della Property 12 è che l'esercente normalizzato del
# movimento DEVE essere presente nel mapping. Per garantire che i lookup
# vadano a segno (`categorizza` usa `normalize_esercente(descrizione)` come
# chiave), costruiamo il mapping indicizzando per la stessa normalizzazione
# delle descrizioni generate.
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

# Valori di categoria/sotto-categoria di default (stringhe non vuote).
_CATEGORIE = ["Spesa", "Casa", "Trasporti", "Svago", "Salute", "Bollette"]
_SOTTO_CATEGORIE = ["Alimentari", "Affitto", "Benzina", "Cinema", "Farmacia"]


@st.composite
def movimento_e_mapping(draw):
    """Genera un movimento e un mapping in cui l'esercente del movimento è presente.

    Costruisce sempre il mapping keyed by `normalize_esercente` della
    descrizione generata, così che il lookup in `categorizza` colpisca la voce.
    Opzionalmente include altre voci (rumore) per irrobustire il test.
    """
    descrizione = draw(st.sampled_from(_DESCRIZIONI))
    esercente_norm = normalize_esercente(descrizione)
    # Garantiamo un esercente non vuoto per questa property (lookup deve hit).
    assume_non_vuoto = esercente_norm != ""
    # In pratica tutte le _DESCRIZIONI normalizzano a non vuoto; se così non
    # fosse hypothesis scarterebbe l'esempio.
    if not assume_non_vuoto:
        descrizione = "Caffè Déjà Vu"
        esercente_norm = normalize_esercente(descrizione)

    categoria = draw(st.sampled_from(_CATEGORIE))
    # La sotto-categoria può essere presente (stringa) oppure assente (None).
    sotto_categoria = draw(st.one_of(st.none(), st.sampled_from(_SOTTO_CATEGORIE)))

    voce = {"categoria": categoria}
    if sotto_categoria is not None:
        voce["sotto_categoria"] = sotto_categoria

    # Mapping keyed per normalizzazione: la voce dell'esercente è sempre presente.
    mapping = {esercente_norm: voce}

    # Aggiungi voci di rumore per altre descrizioni (chiavi diverse).
    altre = draw(
        st.lists(st.sampled_from(_DESCRIZIONI), min_size=0, max_size=4)
    )
    for d in altre:
        chiave = normalize_esercente(d)
        if chiave and chiave != esercente_norm and chiave not in mapping:
            mapping[chiave] = {
                "categoria": draw(st.sampled_from(_CATEGORIE)),
                "sotto_categoria": draw(st.sampled_from(_SOTTO_CATEGORIE)),
            }

    # Il movimento può avere campi pregressi che devono essere sovrascritti.
    movimento = {
        "descrizione": descrizione,
        "importo_eur": draw(st.floats(min_value=-5000, max_value=5000,
                                      allow_nan=False, allow_infinity=False)),
    }

    return movimento, mapping, esercente_norm, categoria, sotto_categoria


@settings(max_examples=100)
@given(dati=movimento_e_mapping())
def test_categorizza_da_mapping_corrente(dati):
    """Esercente presente nel mapping => categoria (e sotto-categoria) assegnate."""
    movimento, mapping, esercente_norm, categoria, sotto_categoria = dati

    risultato = categorizza(movimento, mapping)

    # L'esercente normalizzato deve essere quello atteso ed essere nel mapping.
    assert risultato["esercente_normalizzato"] == esercente_norm
    assert esercente_norm in mapping

    # Categoria di default assegnata dalla voce di mapping.
    assert risultato["categoria"] == categoria

    # Sotto_Categoria assegnata quando presente nella voce; altrimenti None.
    assert risultato["sotto_categoria"] == sotto_categoria

    # Il movimento è categorizzato: il flag da_categorizzare è False.
    assert risultato["da_categorizzare"] is False

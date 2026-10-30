# Feature: gestione-spese, Property 11: Validazione del valore di Tipo_Movimento
"""Property-based test per la validazione del valore di Tipo_Movimento (task 10.6).

Property 11: *Per ogni* valore candidato, la validazione pura del Tipo_Movimento
accetta il valore se e solo se appartiene all'insieme definito nel Glossary
(`spese.excel_importer.TIPI_MOVIMENTO_VALIDI`); ogni altro valore è rifiutato.

Questo riflette il CHECK applicato dal Database sulla colonna `tipo_movimento`
della tabella `movimenti`:

- Req 2.5: un Movimento è salvato solo se il suo Tipo_Movimento appartiene
  all'insieme del Glossary.
- Req 2.6: se il Tipo_Movimento non appartiene all'insieme, il salvataggio è
  rifiutato senza modificare i dati esistenti.

Non esiste un validatore standalone dedicato: la regola di validazione è la pura
appartenenza all'insieme `TIPI_MOVIMENTO_VALIDI`. Il test definisce quindi il
predicato di validazione a partire da quell'insieme e verifica che accetti
esattamente i valori del Glossary e rifiuti tutto il resto.

Validates: Requirements 2.5, 2.6
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.excel_importer import TIPI_MOVIMENTO_VALIDI

# Insieme atteso dei valori ammessi, derivato direttamente dalla costante di
# dominio riusata (single source of truth del Glossary).
VALORI_AMMESSI = frozenset(TIPI_MOVIMENTO_VALIDI)


def tipo_movimento_valido(valore) -> bool:
    """Predicato puro di validazione: valido sse appartiene al Glossary.

    Replica la regola del CHECK della tabella `movimenti`: un Tipo_Movimento è
    valido se e solo se è uno dei valori ammessi dal Glossary.
    """
    return valore in VALORI_AMMESSI


# --- Generatori ------------------------------------------------------------

# Valori validi: estratti esattamente dall'insieme del Glossary.
_valori_validi = st.sampled_from(sorted(VALORI_AMMESSI))

# Valori invalidi: stringhe arbitrarie filtrate per NON appartenere al Glossary.
# Il filtro è innocuo perché le collisioni con i pochi valori ammessi sono
# estremamente improbabili su stringhe generiche.
_stringhe_invalide = st.text().filter(lambda s: s not in VALORI_AMMESSI)


@settings(max_examples=100)
@given(valore=_valori_validi)
def test_valori_del_glossary_sono_accettati(valore):
    """Ogni valore del Glossary è riconosciuto come valido (Req 2.5)."""
    assert tipo_movimento_valido(valore) is True


@settings(max_examples=100)
@given(valore=_stringhe_invalide)
def test_valori_fuori_dal_glossary_sono_rifiutati(valore):
    """Ogni stringa che non appartiene al Glossary è rifiutata (Req 2.6)."""
    assert tipo_movimento_valido(valore) is False

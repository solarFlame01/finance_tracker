# Feature: gestione-spese, Property 10: Mappatura segno -> tipo movimento
"""Property-based test per `spese.pdf.revolut.segno_a_tipo_movimento` (task 8.6).

Property 10: *Per ogni* segno di transazione, la mappatura su Tipo_Movimento è
deterministica e segue l'insieme del Requirement 4.7:

- ``"uscita"`` -> ``"Spese"``
- ``"entrata"`` -> ``"In"``

Validates: Requirements 4.7
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.pdf.revolut import segno_a_tipo_movimento

# Mappatura attesa (oracolo) derivata direttamente dal Requirement 4.7.
_ATTESO = {
    "uscita": "Spese",
    "entrata": "In",
}


@settings(max_examples=100)
@given(segno=st.sampled_from(["uscita", "entrata"]))
def test_segno_a_tipo_movimento(segno):
    """Ogni segno valido mappa sul Tipo_Movimento atteso (Req 4.7)."""
    tipo = segno_a_tipo_movimento(segno)

    # Deterministico e conforme all'oracolo del Requirement 4.7.
    assert tipo == _ATTESO[segno]

    # Verifica puntuale delle due direzioni ammesse.
    if segno == "uscita":
        assert tipo == "Spese"
    else:
        assert tipo == "In"

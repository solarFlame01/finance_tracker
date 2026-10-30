# Feature: gestione-spese, Property 7
"""Property-based test per la validazione dell'upload PDF (task 12.8).

Property 7: *Per ogni* file candidato all'upload dell'estratto conto,
``_valida_upload_pdf`` accetta il file (ritorna ``None``) **se e solo se**
l'estensione del nome e' ``.pdf`` (case-insensitive) **e** la dimensione e'
<= 20 MB; in caso contrario rifiuta restituendo una stringa (motivo del
rifiuto) non vuota, senza avviare alcuna elaborazione (Req 4.1, 4.2).

Validates: Requirements 4.1, 4.2

La funzione sotto test e' pura: dipende solo dagli attributi ``name`` e
``size`` dell'oggetto file. Il test usa un fake minimale con questi due soli
attributi, cosi' da restare indipendente da Streamlit/``UploadedFile`` e da
qualsiasi I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import given, settings
from hypothesis import strategies as st

from views.gestione_spese import _PDF_MAX_BYTES, _valida_upload_pdf


@dataclass
class _FakeUpload:
    """File fittizio con la sola interfaccia usata da ``_valida_upload_pdf``."""

    name: str
    size: int


# Nomi base senza estensione: lettere/cifre/underscore/spazio, anche vuoti.
_basename = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="_ -",
    ),
    min_size=0,
    max_size=20,
)

# Estensioni di esempio, alcune ``.pdf`` (in varie capitalizzazioni) e altre no.
_estensione = st.sampled_from(
    [".pdf", ".PDF", ".Pdf", ".pDf", ".txt", ".csv", ".pd", ".pdfx", "", ".xlsx"]
)

# Dimensioni distribuite sotto, a cavallo e sopra il limite di 20 MB.
_dimensione = st.integers(min_value=0, max_value=_PDF_MAX_BYTES * 2)

# Valori esattamente al/attorno al confine, per stressare la soglia.
_dimensione_confine = st.sampled_from(
    [0, 1, _PDF_MAX_BYTES - 1, _PDF_MAX_BYTES, _PDF_MAX_BYTES + 1]
)


def _e_pdf(nome: str) -> bool:
    return nome.lower().endswith(".pdf")


@settings(max_examples=100)
@given(base=_basename, estensione=_estensione, size=_dimensione | _dimensione_confine)
def test_valida_upload_pdf_accetta_iff_pdf_e_entro_limite(base, estensione, size):
    """Accettato (``None``) IFF estensione ``.pdf`` e dimensione <= 20 MB (Req 4.1/4.2)."""
    nome = f"{base}{estensione}"
    file = _FakeUpload(name=nome, size=size)

    risultato = _valida_upload_pdf(file)

    valido_atteso = _e_pdf(nome) and size <= _PDF_MAX_BYTES

    if valido_atteso:
        # File conforme: nessun motivo di rifiuto.
        assert risultato is None
    else:
        # File non conforme: motivo di rifiuto presente e non vuoto.
        assert isinstance(risultato, str)
        assert risultato.strip() != ""


@settings(max_examples=100)
@given(base=_basename, size=_dimensione_confine)
def test_valida_upload_pdf_pdf_valido_entro_limite_sempre_accettato(base, size):
    """Un ``.pdf`` con dimensione <= limite e' sempre accettato (Req 4.1/4.2)."""
    nome = f"{base}.pdf"
    file = _FakeUpload(name=nome, size=min(size, _PDF_MAX_BYTES))

    assert _valida_upload_pdf(file) is None


@settings(max_examples=100)
@given(base=_basename, estensione=st.sampled_from([".txt", ".csv", ".pd", ".pdfx", ""]))
def test_valida_upload_pdf_estensione_non_pdf_sempre_rifiutata(base, estensione):
    """Qualsiasi estensione diversa da ``.pdf`` e' rifiutata, anche se piccola (Req 4.1)."""
    nome = f"{base}{estensione}"
    file = _FakeUpload(name=nome, size=0)

    risultato = _valida_upload_pdf(file)

    assert isinstance(risultato, str)
    assert risultato.strip() != ""


@settings(max_examples=100)
@given(base=_basename, extra=st.integers(min_value=1, max_value=_PDF_MAX_BYTES))
def test_valida_upload_pdf_pdf_troppo_grande_sempre_rifiutato(base, extra):
    """Un ``.pdf`` oltre il limite di 20 MB e' sempre rifiutato (Req 4.2)."""
    nome = f"{base}.pdf"
    file = _FakeUpload(name=nome, size=_PDF_MAX_BYTES + extra)

    risultato = _valida_upload_pdf(file)

    assert isinstance(risultato, str)
    assert risultato.strip() != ""

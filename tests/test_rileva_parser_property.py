# Feature: gestione-spese, Property 9
"""Property-based test per il rilevamento del formato banca (task 8.5).

Property 9: *Per ogni* estratto conto sintetico prodotto nel formato di una
banca supportata, ``rileva_parser`` restituisce il parser di quella specifica
banca; *per ogni* testo privo dei marcatori di qualsiasi parser registrato,
``rileva_parser`` restituisce ``None`` (Req 4.5).

Validates: Requirements 4.4

Isolamento dallo stato globale
------------------------------
``registra_parser`` muta un registro a livello di modulo
(``spese.pdf.registry._PARSER_REGISTRATI``). Per non dipendere dai parser
registrati all'import (es. il singleton Revolut) né lasciare residui tra i
test, ogni test effettua uno *snapshot* del registro, lo svuota, registra i
propri parser (fake deterministici) e infine ripristina lo stato originale in
un blocco ``finally``.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

import spese.pdf.registry as registry_mod
from spese.pdf.registry import registra_parser, rileva_parser
from spese.pdf.revolut import PARSER as REVOLUT_PARSER
from spese.pdf.revolut import _MARCATORI_RICONOSCIMENTO as REVOLUT_MARCATORI


class _FakeParser:
    """Parser fittizio che riconosce un testo contenente un marcatore univoco.

    Implementa l'interfaccia minima usata dal registry
    (``nome_banca`` + ``riconosce``), così da restare completamente isolato dai
    parser reali e dal loro I/O su ``pdfplumber``.
    """

    def __init__(self, nome_banca: str, marcatore: str) -> None:
        self.nome_banca = nome_banca
        self._marcatore = marcatore.lower()

    def riconosce(self, testo_pdf: str) -> bool:
        if not testo_pdf:
            return False
        return self._marcatore in testo_pdf.lower()

    def estrai_movimenti(self, pdf):  # pragma: no cover - non usato nel test
        return []


class _ParserContext:
    """Context manager che isola il registry: snapshot, reset, restore."""

    def __init__(self, parsers):
        self._parsers = parsers
        self._snapshot: list = []

    def __enter__(self):
        # Snapshot dello stato corrente del registro (copia superficiale).
        self._snapshot = list(registry_mod._PARSER_REGISTRATI)
        registry_mod._PARSER_REGISTRATI.clear()
        for parser in self._parsers:
            registra_parser(parser)
        return self

    def __exit__(self, exc_type, exc, tb):
        # Ripristino esatto dello stato originale, qualunque cosa accada.
        registry_mod._PARSER_REGISTRATI.clear()
        registry_mod._PARSER_REGISTRATI.extend(self._snapshot)
        return False


# Marcatori univoci dei parser fittizi, scelti per non collidere tra loro né
# con i marcatori Revolut.
_MARCATORE_A = "banca-alfa-marker-xyz"
_MARCATORE_B = "banca-beta-marker-qwe"

# Testo "neutro" generato per i casi negativi: NON deve contenere alcun
# marcatore di nessun parser registrato.
_TOKEN_VIETATI = tuple(
    m.lower()
    for m in (_MARCATORE_A, _MARCATORE_B, *REVOLUT_MARCATORI)
)

# Alfabeto sicuro (lettere/cifre/spazi) per comporre testo che non contenga
# accidentalmente un marcatore come sottostringa.
_testo_neutro = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" "),
    min_size=0,
    max_size=80,
).filter(lambda s: not any(tok in s.lower() for tok in _TOKEN_VIETATI))

# Rumore arbitrario da inserire attorno ai marcatori nei casi positivi.
_rumore = st.text(max_size=60)


@settings(max_examples=100)
@given(prefisso=_rumore, suffisso=_rumore)
def test_rileva_parser_restituisce_parser_del_formato_riconosciuto(prefisso, suffisso):
    """Testo col marcatore di una banca -> ``rileva_parser`` ne ritorna il parser (Req 4.4)."""
    parser_a = _FakeParser("Banca Alfa", _MARCATORE_A)
    parser_b = _FakeParser("Banca Beta", _MARCATORE_B)

    with _ParserContext([parser_a, parser_b]):
        testo_a = f"{prefisso} {_MARCATORE_A} {suffisso}"
        testo_b = f"{prefisso} {_MARCATORE_B} {suffisso}"

        rilevato_a = rileva_parser(testo_a)
        rilevato_b = rileva_parser(testo_b)

        # Viene restituito un parser che effettivamente riconosce quel testo.
        assert rilevato_a is parser_a
        assert rilevato_a.riconosce(testo_a)

        assert rilevato_b is parser_b
        assert rilevato_b.riconosce(testo_b)


@settings(max_examples=100)
@given(prefisso=_rumore, suffisso=_rumore)
def test_rileva_parser_revolut_su_marcatori_reali(prefisso, suffisso):
    """Testo coi marcatori reali Revolut -> ritorna il parser Revolut (Req 4.4)."""
    # Usa il parser reale, ma isolato: nessun altro parser registrato.
    with _ParserContext([REVOLUT_PARSER]):
        marcatori = " ".join(REVOLUT_MARCATORI)
        testo = f"{prefisso} {marcatori} {suffisso}"

        rilevato = rileva_parser(testo)

        assert rilevato is REVOLUT_PARSER
        assert rilevato.riconosce(testo)


@settings(max_examples=100)
@given(testo=_testo_neutro)
def test_rileva_parser_none_senza_marcatori(testo):
    """Testo privo di qualsiasi marcatore registrato -> ``None`` (Req 4.5)."""
    parser_a = _FakeParser("Banca Alfa", _MARCATORE_A)
    parser_b = _FakeParser("Banca Beta", _MARCATORE_B)

    with _ParserContext([parser_a, REVOLUT_PARSER, parser_b]):
        assert rileva_parser(testo) is None


@settings(max_examples=100)
@given(prefisso=_rumore, suffisso=_rumore)
def test_rileva_parser_rispetta_ordine_di_registrazione(prefisso, suffisso):
    """Se piu' parser riconoscono il testo, vince il primo registrato (Req 4.4/4.5)."""
    primo = _FakeParser("Primo", _MARCATORE_A)
    secondo = _FakeParser("Secondo", _MARCATORE_A)  # stesso marcatore

    with _ParserContext([primo, secondo]):
        testo = f"{prefisso} {_MARCATORE_A} {suffisso}"
        assert rileva_parser(testo) is primo

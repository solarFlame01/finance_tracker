# Feature: gestione-spese, Property 8: Round-trip del parser PDF per banca
"""Property-based test per il parser PDF Revolut (task 8.4).

Property 8: *Per ogni* transazione generata e *per ogni* banca supportata,
formattando la transazione nel layout testuale di quella banca e ri-parsandola
con il relativo ``BankStatementParser`` si ottengono gli stessi valori di data,
descrizione, importo (2 decimali) e segno.

Qui copriamo la banca Revolut tramite il core puro
``spese.pdf.revolut.estrai_movimenti_da_testo`` (e ``riconosce_testo``).

Strategia del test (round-trip):

1. Si generano transazioni (data, descrizione, importo positivo a 2 decimali,
   segno).
2. Si formattano nel layout testuale Revolut atteso dal parser
   (``Data Descrizione Importo Saldo``), con la data in formato ``"D Mon YYYY"``,
   l'importo col segno esplicito e un saldo progressivo (il parser prende il
   PRIMO valore monetario come importo e l'ultimo come saldo).
3. Si includono i marcatori di riconoscimento (``revolut`` + ``account
   statement``) così che ``riconosce_testo`` sia ``True``.
4. Si ri-parsa il testo e si verifica il round-trip: stessa data, stesso importo
   (2 decimali) e stesso segno; descrizione uguale a meno di spazi.

Validates: Requirements 4.3
"""

from __future__ import annotations

from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from spese.pdf.revolut import estrai_movimenti_da_testo, riconosce_testo

# Abbreviazioni dei mesi in inglese, nell'ordine 1..12, come usate da Revolut.
_MESI_ABBR = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _formatta_data(d: date) -> str:
    """Formatta una data nel layout Revolut ``"D Mon YYYY"`` (giorno senza zero)."""
    return f"{d.day} {_MESI_ABBR[d.month - 1]} {d.year}"


def _formatta_importo(importo: float, segno: str) -> str:
    """Formatta un importo a 2 decimali col segno esplicito del verso.

    Il parser interpreta un segno ``-`` come uscita e l'assenza di segno (o un
    ``+``) come entrata. Usiamo sempre un segno esplicito per determinismo.
    """
    prefisso = "-" if segno == "uscita" else "+"
    return f"{prefisso}{importo:.2f}"


# --- Generatori ------------------------------------------------------------

# Descrizioni "sicure": solo lettere e spazi singoli, non vuote a meno di strip.
# Evitiamo cifre e punti così che nessun pattern monetario (numero con 2
# decimali) compaia nella descrizione e "sporchi" l'estrazione del primo
# importo. Niente simboli valuta per lo stesso motivo.
_PAROLA = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    min_size=1,
    max_size=10,
)
_DESCRIZIONE = st.lists(_PAROLA, min_size=1, max_size=4).map(" ".join)

# Date valide nel range tipico di un estratto conto.
_DATA = st.dates(min_value=date(2000, 1, 1), max_value=date(2099, 12, 31))

# Importo positivo a 2 decimali, senza arrivare al separatore delle migliaia
# (il round-trip del separatore non è il focus di questa property).
_IMPORTO = st.integers(min_value=1, max_value=99999).map(lambda c: round(c / 100.0, 2))

_SEGNO = st.sampled_from(["entrata", "uscita"])

_TRANSAZIONE = st.tuples(_DATA, _DESCRIZIONE, _IMPORTO, _SEGNO)


def _costruisci_testo(transazioni: list[tuple]) -> str:
    """Costruisce il testo sintetico dell'estratto conto Revolut.

    Include un'intestazione con i marcatori di riconoscimento e poi una riga per
    transazione nel layout ``Data Descrizione Importo Saldo`` con saldo
    progressivo.
    """
    righe = [
        "Revolut Bank UAB",
        "Account Statement",
        "Data Descrizione Importo Saldo",
    ]
    saldo = 0.0
    for d, descrizione, importo, segno in transazioni:
        saldo += importo if segno == "entrata" else -importo
        saldo = round(saldo, 2)
        riga = (
            f"{_formatta_data(d)} {descrizione} "
            f"{_formatta_importo(importo, segno)} {saldo:.2f}"
        )
        righe.append(riga)
    return "\n".join(righe)


@settings(max_examples=100)
@given(transazioni=st.lists(_TRANSAZIONE, min_size=1, max_size=8))
def test_round_trip_parser_revolut(transazioni):
    """Round-trip Revolut: format -> parse restituisce gli stessi valori (Req 4.3)."""
    testo = _costruisci_testo(transazioni)

    # Il testo sintetico deve essere riconosciuto come formato Revolut (Req 4.4).
    assert riconosce_testo(testo) is True

    estratte = estrai_movimenti_da_testo(testo)

    # Una transazione estratta per ogni riga generata, nello stesso ordine.
    assert len(estratte) == len(transazioni)

    for (d, descrizione, importo, segno), tx in zip(transazioni, estratte):
        # Nessuna esclusione: la riga è ben formata.
        assert tx.motivo_esclusione is None

        # Data identica.
        assert tx.data == d

        # Importo a 2 decimali, sempre positivo, uguale al generato.
        assert tx.importo_eur is not None
        assert tx.importo_eur == round(importo, 2)
        assert round(tx.importo_eur, 2) == tx.importo_eur

        # Segno (verso) preservato.
        assert tx.segno == segno

        # Descrizione uguale a meno di spazi (whitespace normalizzato).
        assert " ".join(tx.descrizione.split()) == " ".join(descrizione.split())

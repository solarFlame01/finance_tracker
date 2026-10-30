"""Parser concreto dell'estratto conto PDF di Revolut.

Implementa la strategy :class:`BankStatementParser` (Req 4.3/4.4) per gli
estratti conto Revolut, usando ``pdfplumber`` solo per l'I/O di estrazione del
testo dal PDF. Tutta la logica di parsing testuale è separata dall'I/O così da
restare pura e unit/property-testabile (task 8.4) alimentandola con testo
sintetico, senza dipendere da file PDF o da ``pdfplumber``.

Separazione delle responsabilità:

- ``riconosce_testo`` / ``estrai_movimenti_da_testo``: logica PURA che lavora su
  una stringa di testo (nessuna dipendenza da ``pdfplumber``).
- ``estrai_movimenti``: adapter di I/O che estrae il testo dal PDF con
  ``pdfplumber`` (import lazy) e delega al core puro.

Mappatura segno -> Tipo_Movimento (Req 4.7): ``segno_a_tipo_movimento``
classifica ``"uscita" -> "Spese"`` e ``"entrata" -> "In"`` (salvo successiva
riclassificazione come Trasferimento, gestita altrove secondo il Requirement 7).

Esclusione (Req 4.8): le righe riconosciute come transazioni ma prive di data o
di importo estraibili vengono comunque restituite come
:class:`TransazioneEstratta` con ``motivo_esclusione`` valorizzato, così che la
UI possa mostrarle nell'anteprima con il motivo dell'esclusione.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from .base import BankStatementParser, TransazioneEstratta
from .registry import registra_parser

NOME_BANCA = "Revolut"

# Mappa deterministica segno -> Tipo_Movimento (Req 4.7).
_SEGNO_TIPO: dict[str, str] = {
    "uscita": "Spese",
    "entrata": "In",
}

# Intestazioni/marcatori tipici di un estratto conto Revolut, usati per il
# rilevamento del formato (Req 4.4). Il confronto è case-insensitive.
_MARCATORI_RICONOSCIMENTO: tuple[str, ...] = (
    "revolut",
    "account statement",
)

# Abbreviazioni dei mesi in inglese usate da Revolut nelle date (es. "5 Jan 2024").
_MESI = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Data in formato Revolut: "5 Jan 2024" oppure "05 Jan 2024".
_RE_DATA = re.compile(
    r"^\s*(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\s+(.*)$"
)

# Importo monetario con 2 decimali, eventuale separatore delle migliaia e segno.
# Esempi riconosciuti: "12.34", "-12.34", "1,234.56", "€12.34", "12.34 EUR".
_RE_IMPORTO = re.compile(
    r"""
    (?P<segno>[-+])?                 # segno opzionale che precede
    \s*(?:€|EUR)?\s*                 # simbolo/codice valuta opzionale
    (?P<numero>\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})  # numero con 2 decimali
    \s*(?:€|EUR)?                    # simbolo/codice valuta opzionale in coda
    """,
    re.VERBOSE,
)


def segno_a_tipo_movimento(segno: str) -> str:
    """Mappa il segno di una transazione sul Tipo_Movimento (Req 4.7).

    Mappatura deterministica:

    - ``"uscita"`` -> ``"Spese"``
    - ``"entrata"`` -> ``"In"``

    La riclassificazione di una coppia come Trasferimento (Requirement 7) è
    gestita a valle dal riconciliatore e non riguarda questa funzione.

    Args:
        segno: Verso del movimento, ``"uscita"`` o ``"entrata"``.

    Returns:
        Il Tipo_Movimento corrispondente (``"Spese"`` o ``"In"``).

    Raises:
        ValueError: Se ``segno`` non è ``"uscita"`` né ``"entrata"``.
    """
    try:
        return _SEGNO_TIPO[segno]
    except KeyError:
        raise ValueError(
            f"Segno non valido: {segno!r}. Attesi 'uscita' o 'entrata'."
        )


def _parse_data(giorno: str, mese: str, anno: str) -> date | None:
    """Converte i componenti di una data Revolut in :class:`datetime.date`.

    Ritorna ``None`` se il mese non è riconosciuto o la data non è valida
    (es. 31 Feb), così che la riga sia esclusa con motivo (Req 4.8).
    """
    numero_mese = _MESI.get(mese.lower())
    if numero_mese is None:
        return None
    try:
        return date(int(anno), numero_mese, int(giorno))
    except ValueError:
        return None


def _parse_importo(
    match: re.Match | None,
) -> tuple[float, Literal["entrata", "uscita"]] | None:
    """Estrae importo (2 decimali) e segno da un match monetario già individuato.

    Il verso è dato dal segno esplicito: un importo negativo è un'uscita, un
    importo positivo (o senza segno) è un'entrata.

    Negli estratti Revolut il layout di riga è ``Data Descrizione Importo Saldo``:
    l'importo del movimento è il PRIMO valore monetario dopo la descrizione, non
    l'ultimo (che è il saldo progressivo). Il chiamante passa quindi il primo
    match monetario presente dopo la descrizione.

    Args:
        match: Il match di :data:`_RE_IMPORTO` relativo all'importo del
            movimento, oppure ``None`` se nessun importo è presente.

    Returns:
        La coppia ``(importo_eur, segno)`` con ``importo_eur`` sempre positivo a
        2 decimali, oppure ``None`` se ``match`` è ``None`` (Req 4.8).
    """
    if match is None:
        return None

    numero = float(match.group("numero").replace(",", ""))
    segno_esplicito = match.group("segno")
    segno: Literal["entrata", "uscita"] = (
        "uscita" if segno_esplicito == "-" else "entrata"
    )
    return round(abs(numero), 2), segno


def riconosce_testo(testo_pdf: str) -> bool:
    """Rileva se il testo corrisponde al formato Revolut (Req 4.4).

    Logica PURA (nessun I/O): il formato è riconosciuto se il testo contiene
    tutti i marcatori attesi, confrontati case-insensitive.

    Args:
        testo_pdf: Testo estratto dal PDF.

    Returns:
        ``True`` se il testo corrisponde al formato Revolut, altrimenti ``False``.
    """
    if not testo_pdf:
        return False
    testo = testo_pdf.lower()
    return all(marcatore in testo for marcatore in _MARCATORI_RICONOSCIMENTO)


def estrai_movimenti_da_testo(testo_pdf: str) -> list[TransazioneEstratta]:
    """Estrae i movimenti dal testo di un estratto conto Revolut (Req 4.3).

    Logica PURA (nessun I/O): è il core testabile del parser. Scorre le righe
    del testo; una riga è considerata una transazione se inizia con una data nel
    formato Revolut (``"5 Jan 2024 ..."``). Per ogni transazione estrae data,
    descrizione e l'importo (2 decimali) con il relativo segno.

    Gestione delle esclusioni (Req 4.8): se la data non è parsabile o l'importo
    non è estraibile, la riga viene comunque restituita come
    :class:`TransazioneEstratta` con ``motivo_esclusione`` valorizzato (la data
    e/o l'importo mancanti restano ``None``), così da poterla mostrare
    nell'anteprima. Le righe che non iniziano con una data (intestazioni,
    totali, righe vuote) non sono considerate transazioni e vengono ignorate.

    Args:
        testo_pdf: Testo estratto dal PDF (anche sintetico, per i test).

    Returns:
        La lista delle :class:`TransazioneEstratta`, incluse quelle escluse con
        ``motivo_esclusione`` valorizzato.
    """
    transazioni: list[TransazioneEstratta] = []
    if not testo_pdf:
        return transazioni

    for riga in testo_pdf.splitlines():
        match_data = _RE_DATA.match(riga)
        if match_data is None:
            # Non è una riga di transazione (intestazione, totale, vuota).
            continue

        giorno, mese, anno, resto = match_data.groups()
        data_movimento = _parse_data(giorno, mese, anno)

        # Layout Revolut: "Descrizione Importo Saldo". L'importo del movimento è
        # il PRIMO valore monetario dopo la descrizione; il saldo è l'ultimo.
        match_importo = _RE_IMPORTO.search(resto)
        importo_segno = _parse_importo(match_importo)

        # La descrizione è il testo che precede il primo importo monetario.
        if match_importo is not None:
            descrizione = resto[: match_importo.start()].strip()
        else:
            descrizione = resto.strip()

        if data_movimento is None and importo_segno is None:
            motivo = "Data e importo non estraibili"
            transazioni.append(TransazioneEstratta(
                data=None, descrizione=descrizione, importo_eur=None,
                segno="uscita", motivo_esclusione=motivo,
            ))
            continue
        if data_movimento is None:
            _importo, segno = importo_segno  # type: ignore[misc]
            transazioni.append(TransazioneEstratta(
                data=None, descrizione=descrizione, importo_eur=_importo,
                segno=segno, motivo_esclusione="Data non estraibile",
            ))
            continue
        if importo_segno is None:
            transazioni.append(TransazioneEstratta(
                data=data_movimento, descrizione=descrizione, importo_eur=None,
                segno="uscita", motivo_esclusione="Importo non estraibile",
            ))
            continue

        importo, segno = importo_segno
        transazioni.append(TransazioneEstratta(
            data=data_movimento, descrizione=descrizione, importo_eur=importo,
            segno=segno, motivo_esclusione=None,
        ))

    return transazioni


def _estrai_testo_da_pdf(pdf) -> str:
    """Estrae il testo da un PDF con ``pdfplumber`` (unico punto di I/O).

    ``pdfplumber`` è importato in modo lazy per mantenere importabile e testabile
    il resto del modulo anche in assenza della dipendenza.

    Args:
        pdf: Percorso del file, oggetto file binario, o istanza
            ``pdfplumber.PDF`` già aperta.

    Returns:
        Il testo concatenato di tutte le pagine del PDF.
    """
    import pdfplumber

    # Se è già un documento pdfplumber aperto, non lo richiudo.
    if hasattr(pdf, "pages"):
        pagine = pdf.pages
        return "\n".join((pagina.extract_text() or "") for pagina in pagine)

    with pdfplumber.open(pdf) as documento:
        return "\n".join(
            (pagina.extract_text() or "") for pagina in documento.pages
        )


class RevolutParser:
    """Parser dell'estratto conto Revolut (:class:`BankStatementParser`)."""

    nome_banca: str = NOME_BANCA

    def riconosce(self, testo_pdf: str) -> bool:
        """Delega a :func:`riconosce_testo` (Req 4.4)."""
        return riconosce_testo(testo_pdf)

    def estrai_movimenti(self, pdf) -> list[TransazioneEstratta]:
        """Estrae i movimenti dal PDF Revolut (Req 4.3).

        Adapter di I/O: estrae il testo dal PDF con ``pdfplumber`` e delega la
        logica di parsing al core puro :func:`estrai_movimenti_da_testo`.

        Args:
            pdf: Percorso del file, file binario o documento ``pdfplumber``
                aperto. Se è già una stringa di testo, viene usata direttamente
                (comodo per i test).

        Returns:
            La lista delle :class:`TransazioneEstratta` estratte.
        """
        if isinstance(pdf, str):
            # Comodità: consente di passare direttamente il testo (test).
            return estrai_movimenti_da_testo(pdf)
        testo = _estrai_testo_da_pdf(pdf)
        return estrai_movimenti_da_testo(testo)


# Istanza singleton registrata nel registry al momento dell'import del modulo
# (Req 4.4). L'annotazione di tipo serve anche come controllo statico di
# conformità al Protocol BankStatementParser.
PARSER: BankStatementParser = RevolutParser()

registra_parser(PARSER)

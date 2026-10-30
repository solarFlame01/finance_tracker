"""Interfaccia e modello dati per l'estrazione dei movimenti dai PDF.

Modulo di dominio puro: definisce il Protocol `BankStatementParser` (strategy
per banca, Req 4.3/4.4) e la dataclass `TransazioneEstratta`, il contratto che
ogni parser di estratto conto deve produrre. Le transazioni prive di data o
importo vengono rappresentate con `motivo_esclusione` valorizzato (Req 4.8).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol, runtime_checkable


@dataclass
class TransazioneEstratta:
    """Movimento estratto da una riga di estratto conto PDF.

    Attributes:
        data: Data del movimento, oppure ``None`` se non estraibile.
        descrizione: Testo descrittivo grezzo della riga.
        importo_eur: Importo in euro a 2 decimali, oppure ``None`` se non
            estraibile.
        segno: ``"entrata"`` o ``"uscita"`` secondo il verso del movimento.
        motivo_esclusione: Se valorizzato, indica perché la riga è stata
            esclusa (es. data o importo mancante, Req 4.8); ``None`` per le
            transazioni valide.
    """

    data: date | None
    descrizione: str
    importo_eur: float | None
    segno: Literal["entrata", "uscita"]
    motivo_esclusione: str | None = None


@runtime_checkable
class BankStatementParser(Protocol):
    """Strategy di estrazione specifica per banca (Req 4.3/4.4)."""

    nome_banca: str

    def riconosce(self, testo_pdf: str) -> bool:
        """True se il layout/intestazione del PDF corrisponde a questa banca (Req 4.4)."""
        ...

    def estrai_movimenti(self, pdf) -> list[TransazioneEstratta]:
        """Estrae data, descrizione, importo (2 decimali) e segno per ogni riga (Req 4.3).

        Esclude e annota le transazioni senza data/importo valorizzando
        ``motivo_esclusione`` (Req 4.8).
        """
        ...

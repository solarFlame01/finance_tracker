"""Registry dei parser PDF per banca.

Modulo di dominio puro. Mantiene un registro a livello di modulo dei parser
concreti (`BankStatementParser`, Req 4.4) e offre il rilevamento del formato:
`rileva_parser` restituisce il primo parser che riconosce il testo del PDF,
altrimenti ``None`` (Req 4.5).
"""

from __future__ import annotations

from .base import BankStatementParser

# Registro a livello di modulo dei parser disponibili (Req 4.4).
_PARSER_REGISTRATI: list[BankStatementParser] = []


def registra_parser(parser: BankStatementParser) -> None:
    """Registra un parser nel registry a livello di modulo (Req 4.4).

    Args:
        parser: Implementazione di :class:`BankStatementParser` da rendere
            disponibile per il rilevamento del formato.
    """
    _PARSER_REGISTRATI.append(parser)


def rileva_parser(testo_pdf: str) -> BankStatementParser | None:
    """Rileva il parser adatto al formato del PDF (Req 4.4/4.5).

    Scorre i parser registrati nell'ordine di registrazione e ritorna il primo
    il cui ``riconosce(testo_pdf)`` è ``True``; se nessun parser riconosce il
    formato ritorna ``None`` (Req 4.5).

    Args:
        testo_pdf: Testo estratto dal PDF su cui effettuare il rilevamento.

    Returns:
        Il primo :class:`BankStatementParser` che riconosce il formato, oppure
        ``None`` se nessun parser corrisponde.
    """
    for parser in _PARSER_REGISTRATI:
        if parser.riconosce(testo_pdf):
            return parser
    return None

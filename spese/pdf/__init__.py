"""Sotto-package per il parsing degli estratti conto PDF multi-banca.

Contiene l'interfaccia `BankStatementParser`, il registry dei parser e i
parser concreti per banca.

L'import dei moduli dei parser concreti (es. ``revolut``) ha l'effetto
collaterale di registrarli nel registry tramite ``registra_parser``: importare
il package rende quindi i parser disponibili a ``rileva_parser`` (Req 4.4).
"""

# Import dei parser concreti per innescarne la registrazione nel registry.
from . import revolut  # noqa: F401

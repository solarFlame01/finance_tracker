# Feature: gestione-spese, task 7.6: Unit/edge-case test dell'importatore Excel
"""Test unit/edge-case per `spese.excel_importer` (task 7.6).

Coprono due comportamenti di confine dell'Importatore_Excel:

- Req 3.2: se il file caricato non è un `.xlsx` valido/leggibile,
  `leggi_storico_excel` solleva `ExcelNonValido` e `importa_storico` lascia
  propagare l'eccezione SENZA eseguire alcun salvataggio (nessuna delega al
  layer dati viene invocata).

- Req 3.4: una riga priva di campi obbligatori del Movimento è scartata da
  `mappa_riga_a_movimento` (ritorna `None`) ed è conteggiata tra gli
  `scartati` nel riepilogo di `importa_storico`.

Le interazioni con il database sono sostituite da callable fittizie
iniettate, così nessun DB reale viene contattato.

Validates: Requirements 3.2, 3.4
"""

import io

import pandas as pd
import pytest

from spese.excel_importer import (
    ExcelNonValido,
    COLONNE_ATTESE,
    importa_storico,
    leggi_storico_excel,
    mappa_riga_a_movimento,
)


# ---------------------------------------------------------------------------
# Helper: fake callable del layer dati che registrano le invocazioni.
# ---------------------------------------------------------------------------
class _DelegheFittizie:
    """Raccoglie le chiamate alle callable di delega per verificarle nei test."""

    def __init__(self, inseriti=None):
        self.conti = []
        self.categorie = []
        self.sotto_categorie = []
        self.movimenti_upsert = []
        self._inseriti = inseriti

    def get_or_create_conto(self, nome):
        self.conti.append(nome)
        return nome

    def upsert_categoria(self, nome):
        self.categorie.append(nome)
        return nome

    def upsert_sotto_categoria(self, nome, categoria):
        self.sotto_categorie.append((nome, categoria))
        return nome

    def upsert_movimenti(self, movimenti):
        self.movimenti_upsert.append(list(movimenti))
        return self._inseriti

    @property
    def toccato_il_db(self):
        return bool(
            self.conti
            or self.categorie
            or self.sotto_categorie
            or self.movimenti_upsert
        )

    def kwargs(self):
        return {
            "get_or_create_conto": self.get_or_create_conto,
            "upsert_categoria": self.upsert_categoria,
            "upsert_sotto_categoria": self.upsert_sotto_categoria,
            "upsert_movimenti": self.upsert_movimenti,
        }


def _xlsx_bytes(df: pd.DataFrame) -> io.BytesIO:
    """Serializza un DataFrame in un buffer `.xlsx` in memoria."""
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    return buffer


# ===========================================================================
# Req 3.2: file non-.xlsx -> ExcelNonValido, nessun salvataggio.
# ===========================================================================
def test_leggi_storico_excel_file_non_valido_solleva_excel_non_valido():
    """Byte casuali (non un .xlsx) -> `ExcelNonValido` (errore gestito)."""
    file_invalido = io.BytesIO(b"non sono un file excel valido \x00\x01\x02\x03")
    with pytest.raises(ExcelNonValido):
        leggi_storico_excel(file_invalido)


def test_importa_storico_propaga_excel_non_valido_senza_salvare():
    """`importa_storico` propaga `ExcelNonValido` senza toccare il layer dati."""
    deleghe = _DelegheFittizie()
    file_invalido = io.BytesIO(b"\x50\x4b\x03\x04 ma troncato - non uno xlsx")

    with pytest.raises(ExcelNonValido):
        importa_storico(file_invalido, **deleghe.kwargs())

    # Req 3.2: nessun salvataggio deve essere avvenuto.
    assert deleghe.toccato_il_db is False
    assert deleghe.movimenti_upsert == []


def test_importa_storico_file_di_testo_vuoto_non_salva():
    """Anche un buffer vuoto non è un .xlsx: errore gestito, nessun salvataggio."""
    deleghe = _DelegheFittizie()
    with pytest.raises(ExcelNonValido):
        importa_storico(io.BytesIO(b""), **deleghe.kwargs())
    assert deleghe.toccato_il_db is False


# ===========================================================================
# Req 3.4: riga priva di campi obbligatori -> scartata e conteggiata.
# ===========================================================================
def test_mappa_riga_scarta_riga_senza_campi_obbligatori():
    """Riga senza Conto/EUR/Periodo/Tipo valido -> `None` (Req 3.4)."""
    # Manca il Conto (campo obbligatorio).
    riga_senza_conto = {
        "Periodo": "2024-01-15",
        "Conto": None,
        "Categoria": "Spesa",
        "Sotto-categoria": None,
        "Nota": None,
        "EUR": 10.0,
        "Guadagni/Spese": "Spese",
        "Descrizione": "Supermercato",
        "Valuta": "EUR",
    }
    assert mappa_riga_a_movimento(riga_senza_conto) is None


def test_importa_storico_conteggia_righe_scartate():
    """Una riga incompleta è scartata; una valida è importata (Req 3.4)."""
    riga_valida = {
        "Periodo": "2024-02-10",
        "Conto": "Conto Corrente",
        "Categoria": "Alimentari",
        "Sotto-categoria": "Supermercato",
        "Nota": None,
        "EUR": 42.50,
        "Guadagni/Spese": "Spese",
        "Descrizione": "Spesa settimanale",
        "Valuta": "EUR",
    }
    # Riga priva dei campi obbligatori: Conto ed EUR mancanti, tipo non valido.
    riga_scartata = {
        "Periodo": "2024-02-11",
        "Conto": None,
        "Categoria": "Alimentari",
        "Sotto-categoria": None,
        "Nota": None,
        "EUR": None,
        "Guadagni/Spese": "NonValido",
        "Descrizione": "Riga rotta",
        "Valuta": "EUR",
    }
    df = pd.DataFrame([riga_valida, riga_scartata], columns=COLONNE_ATTESE)
    file_xlsx = _xlsx_bytes(df)

    # Il layer dati riporta 1 movimento effettivamente inserito.
    deleghe = _DelegheFittizie(inseriti=1)
    riepilogo = importa_storico(file_xlsx, **deleghe.kwargs())

    assert riepilogo["scartati"] == 1
    assert riepilogo["importati"] == 1
    assert riepilogo["ignorati_presenti"] == 0

    # Invariante: importati + ignorati_presenti + scartati == righe totali (2).
    assert (
        riepilogo["importati"]
        + riepilogo["ignorati_presenti"]
        + riepilogo["scartati"]
        == 2
    )

    # La sola riga valida è stata preparata per l'upsert.
    assert len(deleghe.movimenti_upsert) == 1
    assert len(deleghe.movimenti_upsert[0]) == 1
    assert deleghe.conti == ["Conto Corrente"]

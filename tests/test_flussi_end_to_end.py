# Feature: gestione-spese, task 13.2: integration test end-to-end dei flussi
"""Integration test end-to-end dei flussi Excel e PDF con Supabase MOCKATO.

Questo test esercita i flussi completi senza alcuna rete reale: il "database"
Supabase è sostituito da uno store in-memory (:class:`FakeDB`) che modella
l'upsert idempotente sulla Chiave_Naturale_Movimento con semantica
``ignore_duplicates=True`` (una chiave già presente non viene reinserita né
sovrascritta).

Flusso Excel (Req 3.7, 3.8):
    Si costruisce un piccolo ``.xlsx`` in-memory (pandas -> ``BytesIO``, engine
    openpyxl) con le ``COLONNE_ATTESE``, contenente righe valide e una riga non
    valida. Si invoca ``spese.excel_importer.importa_storico`` iniettando le
    callable del layer dati cablate sullo store. Si verifica il riepilogo
    ``{importati, ignorati_presenti, scartati}`` e poi si ri-esegue l'import
    sullo STESSO file (sovrapposto): la cardinalità dello store non cresce
    (idempotenza).

Flusso PDF (Req 5.1, 5.2, 5.4, 5.5, 5.7):
    Parsing di un testo Revolut sintetico con
    ``spese.pdf.revolut.estrai_movimenti_da_testo``, classificazione
    segno -> Tipo_Movimento, auto-categorizzazione con
    ``spese.categorizzatore.categorizza``, preparazione con
    ``spese.riconciliatore.prepara_per_upsert`` e upsert idempotente nello
    store. Si verificano conteggi (Req 5.5), idempotenza su ricarico
    sovrapposto (Req 5.1, 5.2, 5.4) e il saldo del conto con
    ``spese.riconciliatore.saldo_conto`` (Req 5.7).

Validates: Requirements 3.7, 3.8, 5.1, 5.2, 5.4, 5.5, 5.7
"""

from __future__ import annotations

from datetime import date
from io import BytesIO

import pandas as pd

from spese.categorizzatore import categorizza
from spese.excel_importer import COLONNE_ATTESE, importa_storico
from spese.normalizza import chiave_naturale_movimento
from spese.pdf.revolut import estrai_movimenti_da_testo, segno_a_tipo_movimento
from spese.riconciliatore import prepara_per_upsert, saldo_conto

# Abbreviazioni dei mesi come usate da Revolut (layout "D Mon YYYY").
_MESI_ABBR = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


class FakeDB:
    """Store in-memory che modella Supabase con upsert idempotente.

    I movimenti sono indicizzati per Chiave_Naturale_Movimento, così che
    l'upsert con ``ignore_duplicates=True`` non reinserisca né sovrascriva una
    chiave già presente: è la semantica che garantisce l'idempotenza sui
    ricarichi sovrapposti (Req 3.7, 5.1, 5.2).
    """

    def __init__(self) -> None:
        self.conti: set[str] = set()
        self.categorie: set[str] = set()
        self.sotto_categorie: set[tuple[str, str]] = set()
        # chiave_naturale -> record movimento
        self.movimenti: dict[tuple, dict] = {}

    # --- callable del layer dati iniettabili in importa_storico ---
    def get_or_create_conto(self, nome: str):
        self.conti.add(nome)
        return nome

    def upsert_categoria(self, nome: str):
        self.categorie.add(nome)
        return nome

    def upsert_sotto_categoria(self, nome: str, categoria: str):
        self.sotto_categorie.add((categoria, nome))
        return (categoria, nome)

    def upsert_movimenti(self, movimenti: list[dict]) -> int:
        """Upsert idempotente: ritorna il numero di movimenti NUOVI inseriti.

        Una chiave naturale già presente viene ignorata (ignore_duplicates),
        quindi non incrementa il conteggio degli inseriti (Req 3.8).
        """
        inseriti = 0
        for movimento in movimenti:
            chiave = movimento.get("chiave_naturale")
            if chiave is None:
                chiave = chiave_naturale_movimento(
                    movimento.get("data_movimento"),
                    movimento.get("conto"),
                    movimento.get("importo_eur"),
                    movimento.get("descrizione"),
                )
            if chiave is None:
                continue
            if chiave in self.movimenti:
                # Già presente: ignorato, lo store non cresce.
                continue
            self.movimenti[chiave] = dict(movimento)
            inseriti += 1
        return inseriti

    def movimenti_conto(self, conto: str) -> list[dict]:
        return [m for m in self.movimenti.values() if m.get("conto") == conto]


# --------------------------------------------------------------------------
# Flusso Excel
# --------------------------------------------------------------------------

def _costruisci_xlsx() -> BytesIO:
    """Costruisce un .xlsx in-memory con COLONNE_ATTESE.

    Due righe valide (una spesa, un'entrata) e una riga non valida (manca il
    Conto obbligatorio, Req 3.4) che deve finire tra gli scartati.
    """
    righe = [
        {
            "Periodo": "05-01-2024",
            "Conto": "BBVA",
            "Categoria": "Alimentari",
            "Sotto-categoria": "Supermercato",
            "Nota": None,
            "EUR": -12.50,
            "Guadagni/Spese": "Spese",
            "Descrizione": "ESSELUNGA MILANO",
            "Valuta": "EUR",
        },
        {
            "Periodo": "10-01-2024",
            "Conto": "BBVA",
            "Categoria": "Stipendio",
            "Sotto-categoria": None,
            "Nota": "gennaio",
            "EUR": 1500.00,
            "Guadagni/Spese": "In",
            "Descrizione": "ACME SRL",
            "Valuta": "EUR",
        },
        {
            # Riga non valida: Conto mancante -> scartata (Req 3.4).
            "Periodo": "11-01-2024",
            "Conto": None,
            "Categoria": "Varie",
            "Sotto-categoria": None,
            "Nota": None,
            "EUR": -3.00,
            "Guadagni/Spese": "Spese",
            "Descrizione": "BAR CENTRALE",
            "Valuta": "EUR",
        },
    ]
    df = pd.DataFrame(righe, columns=COLONNE_ATTESE)
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    return buffer


def test_flusso_excel_end_to_end_idempotente():
    """Import Excel completo: riepilogo corretto e idempotenza sul ricarico.

    Validates: Requirements 3.7, 3.8
    """
    db = FakeDB()

    # Primo import: 2 righe valide importate, 1 scartata (Conto mancante).
    riepilogo = importa_storico(
        _costruisci_xlsx(),
        get_or_create_conto=db.get_or_create_conto,
        upsert_categoria=db.upsert_categoria,
        upsert_sotto_categoria=db.upsert_sotto_categoria,
        upsert_movimenti=db.upsert_movimenti,
    )

    assert riepilogo == {"importati": 2, "ignorati_presenti": 0, "scartati": 1}
    assert len(db.movimenti) == 2
    # Conti/categorie/sotto-categorie creati (idempotentemente) dal flusso.
    assert db.conti == {"BBVA"}
    assert db.categorie == {"Alimentari", "Stipendio"}
    assert db.sotto_categorie == {("Alimentari", "Supermercato")}

    cardinalita_dopo_primo = len(db.movimenti)

    # Secondo import dello STESSO file (ricarico sovrapposto): nessun nuovo
    # movimento, tutti ignorati perché già presenti (Req 3.7, 3.8).
    riepilogo2 = importa_storico(
        _costruisci_xlsx(),
        get_or_create_conto=db.get_or_create_conto,
        upsert_categoria=db.upsert_categoria,
        upsert_sotto_categoria=db.upsert_sotto_categoria,
        upsert_movimenti=db.upsert_movimenti,
    )

    assert riepilogo2 == {"importati": 0, "ignorati_presenti": 2, "scartati": 1}
    # La cardinalità dello store NON cresce: idempotenza garantita.
    assert len(db.movimenti) == cardinalita_dopo_primo == 2


# --------------------------------------------------------------------------
# Flusso PDF (Revolut)
# --------------------------------------------------------------------------

def _formatta_data(d: date) -> str:
    return f"{d.day} {_MESI_ABBR[d.month - 1]} {d.year}"


def _costruisci_testo_revolut(transazioni: list[tuple[date, str, float, str]]) -> str:
    """Costruisce il testo sintetico di un estratto conto Revolut.

    Layout per riga: ``Data Descrizione Importo Saldo`` (saldo progressivo),
    con i marcatori di riconoscimento in testa.
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
        prefisso = "-" if segno == "uscita" else "+"
        righe.append(
            f"{_formatta_data(d)} {descrizione} {prefisso}{importo:.2f} {saldo:.2f}"
        )
    return "\n".join(righe)


# Transazioni sintetiche: due uscite e un'entrata su un singolo conto.
_TRANSAZIONI_REVOLUT = [
    (date(2024, 3, 1), "ESSELUNGA MILANO", 12.50, "uscita"),
    (date(2024, 3, 2), "ACME SRL STIPENDIO", 1500.00, "entrata"),
    (date(2024, 3, 3), "BAR CENTRALE ROMA", 3.00, "uscita"),
]

# Mapping esercente_normalizzato -> voce di categoria (riflette correzioni
# manuali pregresse, Req 6.7). Solo due esercenti sono mappati; il terzo resta
# da categorizzare, senza influire su chiave/conteggi/saldo.
_MAPPING = {
    "esselunga milano": {"categoria": "Alimentari", "sotto_categoria": "Supermercato"},
    "acme srl stipendio": {"categoria": "Stipendio", "sotto_categoria": None},
}


def _pipeline_pdf(db: FakeDB, testo: str, conto: str) -> dict:
    """Esegue il flusso PDF: parse -> tipo -> categorizza -> prepara -> upsert.

    Ritorna il dizionario di ``prepara_per_upsert`` arricchito con il numero di
    movimenti effettivamente inseriti dallo store (``inseriti``).
    """
    estratte = estrai_movimenti_da_testo(testo)

    movimenti = []
    for tx in estratte:
        if tx.motivo_esclusione is not None:
            continue
        # Importo con segno incorporato: uscita negativa, entrata positiva.
        tipo = segno_a_tipo_movimento(tx.segno)
        importo = -tx.importo_eur if tx.segno == "uscita" else tx.importo_eur
        movimento = {
            "data_movimento": tx.data.strftime("%Y-%m-%d"),
            "descrizione": tx.descrizione,
            "importo_eur": round(importo, 2),
            "tipo_movimento": tipo,
        }
        movimenti.append(categorizza(movimento, _MAPPING))

    preparato = prepara_per_upsert(movimenti, conto)
    inseriti = db.upsert_movimenti(preparato["validi"])
    preparato["inseriti"] = inseriti
    return preparato


def test_flusso_pdf_end_to_end_idempotente_e_saldo():
    """Flusso PDF completo: conteggi, idempotenza su ricarico e saldo conto.

    Validates: Requirements 5.1, 5.2, 5.4, 5.5, 5.7
    """
    db = FakeDB()
    conto = "Revolut"
    testo = _costruisci_testo_revolut(_TRANSAZIONI_REVOLUT)

    # Primo caricamento: 3 transazioni valide, 0 scartate (Req 5.5).
    primo = _pipeline_pdf(db, testo, conto)
    assert primo["conteggi"] == {"nuovi": 3, "gia_presenti": 0, "scartati": 0}
    assert primo["inseriti"] == 3
    assert len(db.movimenti) == 3

    # La categorizzazione ha agganciato i due esercenti mappati.
    categorie = {m["descrizione_normalizzata"]: m.get("categoria")
                 for m in db.movimenti.values()}
    assert categorie["esselunga milano"] == "Alimentari"
    assert categorie["acme srl stipendio"] == "Stipendio"
    # Il terzo esercente non è mappato: resta da categorizzare.
    assert categorie["bar centrale roma"] is None

    # Saldo del conto: +1500 - 12.50 - 3.00 = 1484.50 (Req 5.7).
    saldo = saldo_conto(db.movimenti_conto(conto))
    assert round(saldo, 2) == 1484.50

    cardinalita_dopo_primo = len(db.movimenti)

    # Secondo caricamento dello STESSO estratto (ricarico sovrapposto): nessun
    # nuovo movimento inserito, store invariato (Req 5.1, 5.2, 5.4).
    secondo = _pipeline_pdf(db, testo, conto)
    assert secondo["conteggi"]["nuovi"] == 3  # tutti validi, ma...
    assert secondo["inseriti"] == 0  # ...già presenti: nessun inserimento
    assert len(db.movimenti) == cardinalita_dopo_primo == 3

    # Il saldo resta invariato dopo il ricarico idempotente (Req 5.7).
    assert round(saldo_conto(db.movimenti_conto(conto)), 2) == 1484.50


def test_flusso_pdf_ricarico_parziale_sovrapposto():
    """Un estratto che aggiunge una nuova transazione a quelle già presenti.

    Le transazioni sovrapposte sono ignorate (stessa chiave naturale) e solo la
    nuova viene inserita, mantenendo l'idempotenza sul sottoinsieme sovrapposto
    (Req 5.1, 5.2, 5.4).
    """
    db = FakeDB()
    conto = "Revolut"

    _pipeline_pdf(db, _costruisci_testo_revolut(_TRANSAZIONI_REVOLUT), conto)
    assert len(db.movimenti) == 3

    # Estratto sovrapposto: le 3 originali + una nuova transazione.
    esteso = _TRANSAZIONI_REVOLUT + [
        (date(2024, 3, 4), "FARMACIA SAN MARCO", 8.90, "uscita"),
    ]
    secondo = _pipeline_pdf(db, _costruisci_testo_revolut(esteso), conto)

    # 4 validi preparati, ma solo 1 nuovo effettivamente inserito.
    assert secondo["conteggi"]["nuovi"] == 4
    assert secondo["inseriti"] == 1
    assert len(db.movimenti) == 4

    # Saldo aggiornato: 1484.50 - 8.90 = 1475.60 (Req 5.7).
    assert round(saldo_conto(db.movimenti_conto(conto)), 2) == 1475.60

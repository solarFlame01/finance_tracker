# Feature: gestione-spese, task 12.9: Unit/edge-case e smoke test della UI
"""Unit/edge-case + smoke test della UI della Sezione_Gestione_Spese (task 12.9).

Questi test privilegiano controlli leggeri che NON richiedono il rendering di
Streamlit: dove possibile esercitano direttamente la logica pura (importatore
Excel, parser PDF, helper di rilevamento trasferimenti) e, per i comportamenti
intrecciati con i widget Streamlit, usano l'ispezione statica del sorgente.

Copertura (requisiti del task 12.9):

- Smoke (1.5): `views.gestione_spese` definisce `render_gestione_spese`
  invocabile e `app.py` contiene il ramo di routing per "gestione_spese".
- Default valuta EUR (2.9): `mappa_riga_a_movimento` imposta valuta='EUR'
  quando la colonna Valuta è assente/vuota.
- Salvataggio senza sotto-categoria (2.11): `mappa_riga_a_movimento` senza
  Sotto-categoria produce comunque un Movimento valido con
  `sotto_categoria=None`; inoltre `prepara_per_upsert` accetta movimenti privi
  di sotto-categoria.
- Anteprima con conteggi (4.6): usando il core puro del parser Revolut
  (`estrai_movimenti_da_testo`) su testo sintetico, importabili + escluse ==
  totale transazioni riconosciute, come nella logica dell'anteprima.
- Inserimento lato trasferimento mancante (7.6): il rilevatore puro
  `_trova_lati_trasferimento_isolati` individua un lato uscita senza la sua
  entrata speculare e non segnala nulla su un insieme completamente appaiato.
- Conferma operazione entro il flusso (9.4): i percorsi di successo della UI
  mostrano conferme via `st.success` (ispezione del sorgente).

Validates: Requirements 2.9, 2.11, 4.6, 7.6, 9.4, 1.5
"""

import re
from pathlib import Path

import pytest

from spese.excel_importer import mappa_riga_a_movimento
from spese.pdf.revolut import estrai_movimenti_da_testo
from spese.riconciliatore import prepara_per_upsert
from views import gestione_spese
from views.gestione_spese import _trova_lati_trasferimento_isolati

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PY = PROJECT_ROOT / "app.py"
GESTIONE_SPESE_PY = PROJECT_ROOT / "views" / "gestione_spese.py"


@pytest.fixture(scope="module")
def app_source():
    return APP_PY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def ui_source():
    return GESTIONE_SPESE_PY.read_text(encoding="utf-8")


def _riga_base(**override) -> dict:
    """Riga storica Excel valida (campi obbligatori presenti) personalizzabile."""
    riga = {
        "Periodo": "2024-03-01",
        "Conto": "Conto Corrente",
        "Categoria": "Alimentari",
        "Sotto-categoria": "Supermercato",
        "Nota": None,
        "EUR": 25.0,
        "Guadagni/Spese": "Spese",
        "Descrizione": "Spesa settimanale",
        "Valuta": "EUR",
    }
    riga.update(override)
    return riga


# ===========================================================================
# Smoke (1.5): render_gestione_spese e ramo di routing in app.py
# ===========================================================================
def test_render_gestione_spese_e_invocabile():
    """`views.gestione_spese` espone `render_gestione_spese` invocabile (1.5)."""
    assert hasattr(gestione_spese, "render_gestione_spese")
    assert callable(gestione_spese.render_gestione_spese)


def test_app_ha_ramo_routing_gestione_spese(app_source):
    """`app.py` importa e instrada verso `render_gestione_spese` (1.5)."""
    assert re.search(
        r"from\s+views\.gestione_spese\s+import\s+render_gestione_spese",
        app_source,
    ), "app.py deve importare render_gestione_spese"
    assert re.search(
        r"st\.session_state\.page\s*==\s*[\"']gestione_spese[\"']",
        app_source,
    ), "app.py deve contenere il ramo di routing per 'gestione_spese'"
    assert re.search(r"render_gestione_spese\s*\(\s*\)", app_source), (
        "app.py deve invocare render_gestione_spese() nel ramo di routing"
    )


# ===========================================================================
# Default valuta EUR (2.9)
# ===========================================================================
def test_valuta_default_eur_quando_colonna_assente():
    """Senza la chiave 'Valuta' la valuta del movimento è 'EUR' (2.9)."""
    riga = _riga_base()
    del riga["Valuta"]
    movimento = mappa_riga_a_movimento(riga)
    assert movimento is not None
    assert movimento["valuta"] == "EUR"


@pytest.mark.parametrize("valore_valuta", [None, "", "   "])
def test_valuta_default_eur_quando_cella_vuota(valore_valuta):
    """Cella Valuta vuota/assente -> default 'EUR' (2.9)."""
    movimento = mappa_riga_a_movimento(_riga_base(Valuta=valore_valuta))
    assert movimento is not None
    assert movimento["valuta"] == "EUR"


def test_valuta_esplicita_viene_preservata():
    """Una valuta esplicita non viene sovrascritta dal default (2.9)."""
    movimento = mappa_riga_a_movimento(_riga_base(Valuta="USD"))
    assert movimento is not None
    assert movimento["valuta"] == "USD"


# ===========================================================================
# Salvataggio senza sotto-categoria (2.11)
# ===========================================================================
def test_movimento_valido_senza_sotto_categoria():
    """Senza Sotto-categoria il movimento è valido con sotto_categoria=None (2.11)."""
    movimento = mappa_riga_a_movimento(_riga_base(**{"Sotto-categoria": None}))
    assert movimento is not None
    assert movimento["sotto_categoria"] is None
    # I campi obbligatori restano valorizzati.
    assert movimento["conto"] == "Conto Corrente"
    assert movimento["tipo_movimento"] == "Spese"


def test_movimento_valido_con_sotto_categoria_mancante_nella_riga():
    """Chiave 'Sotto-categoria' del tutto assente -> movimento valido (2.11)."""
    riga = _riga_base()
    del riga["Sotto-categoria"]
    movimento = mappa_riga_a_movimento(riga)
    assert movimento is not None
    assert movimento["sotto_categoria"] is None


def test_prepara_per_upsert_accetta_movimento_senza_sotto_categoria():
    """`prepara_per_upsert` accetta transazioni prive di sotto_categoria (2.11)."""
    transazione = {
        "data_movimento": "2024-03-01",
        "importo_eur": 25.0,
        "descrizione": "Spesa settimanale",
        # nessuna chiave 'sotto_categoria'
    }
    esito = prepara_per_upsert([transazione], "Conto Corrente")
    assert esito["conteggi"]["nuovi"] == 1
    assert esito["conteggi"]["scartati"] == 0
    assert len(esito["validi"]) == 1
    assert "sotto_categoria" not in esito["validi"][0]


# ===========================================================================
# Anteprima con conteggi (4.6)
# ===========================================================================
def test_anteprima_conteggi_importabili_piu_escluse_coerente():
    """importabili + escluse == totale transazioni riconosciute (4.6).

    Testo sintetico Revolut con 2 transazioni importabili e 1 esclusa (importo
    non estraibile). Replica la logica di anteprima del tab Import Estratto
    Conto che separa `importabili` da `escluse` in base a `motivo_esclusione`.
    """
    testo = "\n".join(
        [
            "Revolut Account Statement",
            "Data Descrizione Importo Saldo",
            "5 Jan 2024 Supermercato -12.34 100.00",
            "6 Jan 2024 Stipendio 1,500.00 1600.00",
            "7 Jan 2024 Riga senza importo",  # esclusa: importo non estraibile
            "",  # riga vuota: non è una transazione, deve essere ignorata
            "Totale pagina",  # intestazione/totale: ignorata
        ]
    )

    transazioni = estrai_movimenti_da_testo(testo)

    importabili = [t for t in transazioni if t.motivo_esclusione is None]
    escluse = [t for t in transazioni if t.motivo_esclusione is not None]

    # Invariante dell'anteprima (Req 4.6): i due gruppi partizionano il totale.
    assert len(importabili) + len(escluse) == len(transazioni)
    # Le righe non-transazione (vuote/totali) non sono conteggiate.
    assert len(transazioni) == 3
    assert len(importabili) == 2
    assert len(escluse) == 1
    # L'esclusa riporta un motivo non vuoto, usato nell'anteprima.
    assert escluse[0].motivo_esclusione


def test_anteprima_senza_transazioni_conteggi_a_zero():
    """Testo privo di transazioni -> entrambi i conteggi a 0 (4.6)."""
    testo = "Revolut Account Statement\nIntestazione senza movimenti\n"
    transazioni = estrai_movimenti_da_testo(testo)
    importabili = [t for t in transazioni if t.motivo_esclusione is None]
    escluse = [t for t in transazioni if t.motivo_esclusione is not None]
    assert len(importabili) == 0
    assert len(escluse) == 0
    assert len(transazioni) == 0


# ===========================================================================
# Inserimento lato trasferimento mancante (7.6)
# ===========================================================================
def test_lato_uscita_isolato_viene_rilevato():
    """Un'uscita senza l'entrata speculare è un lato isolato (7.6)."""
    movimenti = [
        {
            "id": 1,
            "tipo_movimento": "Trasferimento uscita",
            "data_movimento": "2024-04-01",
            "importo_eur": -100.0,
            "conto_id": 10,
        },
        # Movimento non correlato: non deve fungere da controparte.
        {
            "id": 2,
            "tipo_movimento": "Spese",
            "data_movimento": "2024-04-01",
            "importo_eur": -100.0,
            "conto_id": 20,
        },
    ]
    isolati = _trova_lati_trasferimento_isolati(movimenti)
    assert [m["id"] for m in isolati] == [1]


def test_coppia_completa_non_produce_lati_isolati():
    """Uscita + entrata speculari (stessa data/importo, conti diversi) -> nessun isolato (7.6)."""
    movimenti = [
        {
            "id": 1,
            "tipo_movimento": "Trasferimento uscita",
            "data_movimento": "2024-04-01",
            "importo_eur": -100.0,
            "conto_id": 10,
        },
        {
            "id": 2,
            "tipo_movimento": "Trasferimento ingresso",
            "data_movimento": "2024-04-01",
            "importo_eur": 100.0,
            "conto_id": 20,
        },
    ]
    assert _trova_lati_trasferimento_isolati(movimenti) == []


def test_entrata_isolata_viene_rilevata():
    """Un'entrata senza l'uscita speculare è un lato isolato (7.6)."""
    movimenti = [
        {
            "id": 7,
            "tipo_movimento": "Trasferimento ingresso",
            "data_movimento": "2024-05-10",
            "importo_eur": 250.0,
            "conto_id": 30,
        },
    ]
    isolati = _trova_lati_trasferimento_isolati(movimenti)
    assert [m["id"] for m in isolati] == [7]


def test_stesso_conto_non_vale_come_speculare():
    """Una controparte sullo stesso conto non chiude la coppia (7.6)."""
    movimenti = [
        {
            "id": 1,
            "tipo_movimento": "Trasferimento uscita",
            "data_movimento": "2024-06-01",
            "importo_eur": -50.0,
            "conto_id": 10,
        },
        {
            "id": 2,
            "tipo_movimento": "Trasferimento ingresso",
            "data_movimento": "2024-06-01",
            "importo_eur": 50.0,
            "conto_id": 10,  # stesso conto: non è un trasferimento valido
        },
    ]
    isolati = _trova_lati_trasferimento_isolati(movimenti)
    assert {m["id"] for m in isolati} == {1, 2}


def test_nessun_trasferimento_nessun_lato_isolato():
    """Senza movimenti di trasferimento non ci sono lati isolati (7.6)."""
    movimenti = [
        {"id": 1, "tipo_movimento": "Spese", "data_movimento": "2024-06-01",
         "importo_eur": -20.0, "conto_id": 10},
        {"id": 2, "tipo_movimento": "In", "data_movimento": "2024-06-02",
         "importo_eur": 30.0, "conto_id": 10},
    ]
    assert _trova_lati_trasferimento_isolati(movimenti) == []


# ===========================================================================
# Conferma operazione entro il flusso (9.4) - ispezione del sorgente
# ===========================================================================
def test_percorsi_di_successo_mostrano_conferme(ui_source):
    """I flussi di successo della UI usano `st.success` per confermare (9.4)."""
    assert "st.success" in ui_source, (
        "La UI deve mostrare conferme con st.success nei percorsi di successo"
    )
    # Deve esserci più di una conferma (import, trasferimento, modifiche...).
    assert ui_source.count("st.success") >= 3


def test_conferme_presenti_nei_flussi_chiave(ui_source):
    """Import Excel e registrazione trasferimento confermano l'esito (9.4)."""
    # Conferma di import completato (tab Excel / PDF).
    assert "Import completato" in ui_source
    # Conferma di registrazione del trasferimento (tab Trasferimenti).
    assert "Trasferimento" in ui_source and "registrato" in ui_source

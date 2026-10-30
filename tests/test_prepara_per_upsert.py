# Feature: gestione-spese, task 5.4: prepara_per_upsert
"""Unit test per `spese.riconciliatore.prepara_per_upsert` (task 5.4).

Verifica che la funzione:
- calcoli la Chiave_Naturale_Movimento per ogni transazione usando il `conto`
  passato come argomento;
- separi le transazioni in `validi` (chiave calcolabile) e `scartati` (chiave
  non calcolabile -> None, Req 5.3);
- restituisca conteggi sempre presenti, con 0 per le categorie prive di
  movimenti (Req 5.5);
- prepari i record validi per l'upsert aggiungendo `conto`,
  `descrizione_normalizzata` e `chiave_naturale`, senza mutare l'input.
"""

from spese.normalizza import chiave_naturale_movimento
from spese.riconciliatore import prepara_per_upsert


def _tx(data, importo, descrizione, **extra):
    return {
        "data_movimento": data,
        "importo_eur": importo,
        "descrizione": descrizione,
        **extra,
    }


def test_transazione_valida_pronta_per_upsert():
    """Una transazione con chiave calcolabile finisce tra i validi arricchita."""
    tx = _tx("2024-01-05", -12.5, "ESSELUNGA MILANO")
    res = prepara_per_upsert([tx], "BBVA")

    assert res["conteggi"] == {"nuovi": 1, "gia_presenti": 0, "scartati": 0}
    assert res["scartati"] == []
    assert len(res["validi"]) == 1

    record = res["validi"][0]
    attesa = chiave_naturale_movimento("2024-01-05", "BBVA", -12.5, "ESSELUNGA MILANO")
    assert record["conto"] == "BBVA"
    assert record["chiave_naturale"] == attesa
    assert record["descrizione_normalizzata"] == attesa[3]
    # campi originali preservati nella copia
    assert record["importo_eur"] == -12.5
    assert record["descrizione"] == "ESSELUNGA MILANO"


def test_chiave_non_calcolabile_viene_scartata():
    """Importo mancante o descrizione vuota -> scartati (Req 5.3)."""
    senza_importo = _tx("2024-01-06", None, "COOP")
    descrizione_vuota = _tx("2024-01-07", 3.0, "   ")
    res = prepara_per_upsert([senza_importo, descrizione_vuota], "BBVA")

    assert res["conteggi"] == {"nuovi": 0, "gia_presenti": 0, "scartati": 2}
    assert res["validi"] == []
    assert len(res["scartati"]) == 2


def test_conto_argomento_usato_per_la_chiave():
    """Il conto usato è quello passato, non quello eventualmente nella transazione."""
    tx = _tx("2024-01-05", -1.0, "BAR", conto="ALTRO")
    res = prepara_per_upsert([tx], "N26")

    record = res["validi"][0]
    assert record["conto"] == "N26"
    assert record["chiave_naturale"][1] == "N26"


def test_conto_vuoto_scarta_tutto():
    """Conto vuoto -> chiave non calcolabile -> tutto scartato (Req 5.3)."""
    tx = _tx("2024-01-05", -1.0, "BAR")
    res = prepara_per_upsert([tx], "")

    assert res["conteggi"] == {"nuovi": 0, "gia_presenti": 0, "scartati": 1}
    assert res["validi"] == []


def test_fallback_su_chiave_data():
    """La data può provenire dalla chiave grezza `data` (provenienza PDF)."""
    tx = {"data": "2024-02-02", "importo_eur": 5.0, "descrizione": "BAR"}
    res = prepara_per_upsert([tx], "N26")

    assert res["conteggi"]["nuovi"] == 1
    assert res["validi"][0]["chiave_naturale"][0] == "2024-02-02"


def test_lista_vuota_conteggi_a_zero():
    """Lista vuota -> conteggi tutti a 0 (Req 5.5)."""
    res = prepara_per_upsert([], "BBVA")
    assert res == {
        "validi": [],
        "scartati": [],
        "conteggi": {"nuovi": 0, "gia_presenti": 0, "scartati": 0},
    }


def test_none_in_ingresso_non_rompe():
    """Input None -> nessun record, conteggi a 0, senza errori (Req 5.5)."""
    res = prepara_per_upsert(None, "BBVA")
    assert res["conteggi"] == {"nuovi": 0, "gia_presenti": 0, "scartati": 0}


def test_elementi_non_dict_ignorati():
    """Elementi non-dict nella lista sono ignorati senza interrompere."""
    tx = _tx("2024-01-05", -1.0, "BAR")
    res = prepara_per_upsert([None, "x", tx, 42], "BBVA")
    assert res["conteggi"]["nuovi"] == 1
    assert len(res["validi"]) == 1


def test_input_non_mutato():
    """Le transazioni di input non vengono mutate (si restituiscono copie)."""
    tx = _tx("2024-01-05", -1.0, "BAR")
    prepara_per_upsert([tx], "BBVA")
    assert "conto" not in tx
    assert "chiave_naturale" not in tx
    assert "descrizione_normalizzata" not in tx


def test_ordine_preservato_nei_gruppi():
    """L'ordine relativo è preservato all'interno di validi e scartati."""
    v1 = _tx("2024-01-01", -1.0, "ALFA")
    s1 = _tx("2024-01-02", None, "BETA")  # scartato: importo mancante
    v2 = _tx("2024-01-03", -2.0, "GAMMA")
    s2 = _tx("2024-01-04", 1.0, "   ")  # scartato: descrizione vuota
    res = prepara_per_upsert([v1, s1, v2, s2], "BBVA")

    assert [r["descrizione"] for r in res["validi"]] == ["ALFA", "GAMMA"]
    assert [r["descrizione"] for r in res["scartati"]] == ["BETA", "   "]

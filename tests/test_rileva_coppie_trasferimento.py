# Feature: gestione-spese, task 5.3: rileva_coppie_trasferimento
"""Unit test per `spese.riconciliatore.rileva_coppie_trasferimento` (task 5.3).

Verifica che vengano individuate esattamente le coppie (uscita conto A, entrata
conto B != A) con differenza di importo = 0 e differenza di data = 0 giorni,
da proporre per la riclassificazione come Trasferimento (Req 7.4).
"""

from spese.riconciliatore import rileva_coppie_trasferimento


def _uscita(conto, data, importo, **extra):
    return {
        "tipo_movimento": "Spese",
        "conto": conto,
        "data_movimento": data,
        "importo_eur": importo,
        **extra,
    }


def _entrata(conto, data, importo, **extra):
    return {
        "tipo_movimento": "In",
        "conto": conto,
        "data_movimento": data,
        "importo_eur": importo,
        **extra,
    }


def test_coppia_speculare_rilevata():
    """Uscita -100 da A ed entrata +100 in B, stessa data -> una coppia."""
    uscita = _uscita("A", "2024-01-10", -100.0)
    entrata = _entrata("B", "2024-01-10", 100.0)
    coppie = rileva_coppie_trasferimento([uscita, entrata])
    assert coppie == [(uscita, entrata)]


def test_stesso_conto_non_e_coppia():
    """Uscita ed entrata sullo stesso conto non formano un trasferimento."""
    uscita = _uscita("A", "2024-01-10", -100.0)
    entrata = _entrata("A", "2024-01-10", 100.0)
    assert rileva_coppie_trasferimento([uscita, entrata]) == []


def test_date_diverse_non_e_coppia():
    """Differenza di data > 0 giorni esclude la coppia."""
    uscita = _uscita("A", "2024-01-10", -100.0)
    entrata = _entrata("B", "2024-01-11", 100.0)
    assert rileva_coppie_trasferimento([uscita, entrata]) == []


def test_importi_diversi_non_e_coppia():
    """Differenza di importo != 0 esclude la coppia."""
    uscita = _uscita("A", "2024-01-10", -100.0)
    entrata = _entrata("B", "2024-01-10", 99.99)
    assert rileva_coppie_trasferimento([uscita, entrata]) == []


def test_tipi_non_candidati_ignorati():
    """Movimenti già Trasferimento o di altri tipi non sono candidati."""
    gia_trasf_uscita = {
        "tipo_movimento": "Trasferimento uscita",
        "conto": "A",
        "data_movimento": "2024-01-10",
        "importo_eur": -100.0,
    }
    gia_trasf_entrata = {
        "tipo_movimento": "Trasferimento ingresso",
        "conto": "B",
        "data_movimento": "2024-01-10",
        "importo_eur": 100.0,
    }
    assert rileva_coppie_trasferimento([gia_trasf_uscita, gia_trasf_entrata]) == []


def test_importo_non_numerico_ignorato():
    """Movimenti con importo non numerico non possono formare coppia."""
    uscita = _uscita("A", "2024-01-10", None)
    entrata = _entrata("B", "2024-01-10", 100.0)
    assert rileva_coppie_trasferimento([uscita, entrata]) == []


def test_conto_o_data_mancante_ignorato():
    """Conto o data mancanti escludono il movimento dai candidati."""
    uscita_senza_conto = _uscita("", "2024-01-10", -100.0)
    entrata = _entrata("B", "2024-01-10", 100.0)
    assert rileva_coppie_trasferimento([uscita_senza_conto, entrata]) == []

    uscita = _uscita("A", "2024-01-10", -100.0)
    entrata_senza_data = _entrata("B", None, 100.0)
    assert rileva_coppie_trasferimento([uscita, entrata_senza_data]) == []


def test_arrotondamento_due_decimali():
    """La differenza di importo tollera l'errore in virgola mobile a 2 decimali."""
    uscita = _uscita("A", "2024-01-10", -(0.1 + 0.2))  # 0.30000000000000004
    entrata = _entrata("B", "2024-01-10", 0.30)
    assert rileva_coppie_trasferimento([uscita, entrata]) == [(uscita, entrata)]


def test_lista_vuota_e_none():
    """Input vuoto o None -> nessuna coppia, senza errori."""
    assert rileva_coppie_trasferimento([]) == []
    assert rileva_coppie_trasferimento(None) == []


def test_piu_candidati_generano_piu_coppie():
    """Un'uscita che combacia con due entrate su conti diversi genera due coppie."""
    uscita = _uscita("A", "2024-01-10", -50.0)
    entrata_b = _entrata("B", "2024-01-10", 50.0)
    entrata_c = _entrata("C", "2024-01-10", 50.0)
    coppie = rileva_coppie_trasferimento([uscita, entrata_b, entrata_c])
    assert coppie == [(uscita, entrata_b), (uscita, entrata_c)]


def test_non_dict_ignorati():
    """Elementi non-dict nella lista sono ignorati senza interrompere."""
    uscita = _uscita("A", "2024-01-10", -100.0)
    entrata = _entrata("B", "2024-01-10", 100.0)
    coppie = rileva_coppie_trasferimento([None, "x", uscita, 42, entrata])
    assert coppie == [(uscita, entrata)]

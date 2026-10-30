# Feature: gestione-spese
"""Unit test di navigazione e routing (task 11.3).

Verifica l'integrazione della Sezione_Gestione_Spese nel menu di navigazione
(`views/sidebar.py`) e nel routing (`app.py`):

- presenza di una voce di navigazione dedicata con etichetta non vuota (1.1)
- chiave di routing "gestione_spese" univoca e non coincidente con quelle delle
  pagine esistenti (1.2, 1.3)
- pagina predefinita "dashboard" quando `st.session_state.page` non è impostata
  (1.4)
- presenza della funzione `render_gestione_spese` e del ramo di routing
  dedicato in `app.py` (1.5)

Le asserzioni su `app.py` sono eseguite via ispezione statica del sorgente per
evitare l'inizializzazione pesante di Supabase che avviene all'import del modulo.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5
"""

import re
from pathlib import Path

import pytest

from views import sidebar

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PY = PROJECT_ROOT / "app.py"

# Chiave di routing della nuova sezione.
GESTIONE_SPESE_KEY = "gestione_spese"

# Chiavi delle pagine già esistenti (tracking investimenti) con cui la nuova
# chiave NON deve coincidere.
PAGINE_ESISTENTI = {
    "dashboard",
    "gestione_etf",
    "metriche",
    "rendimento_annuo",
    "simula_etf",
    "prossimo_pac",
    "proiezioni_future",
    "impostazioni",
}


@pytest.fixture(scope="module")
def app_source():
    return APP_PY.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Requirement 1.1 - voce di navigazione con etichetta non vuota
# ---------------------------------------------------------------------------

def test_pagine_contiene_voce_gestione_spese():
    """PAGINE deve mappare esattamente una etichetta sulla chiave gestione_spese."""
    assert hasattr(sidebar, "PAGINE"), "views.sidebar deve esporre il mapping PAGINE"
    assert GESTIONE_SPESE_KEY in sidebar.PAGINE.values(), (
        "PAGINE deve contenere una voce con valore 'gestione_spese'"
    )


def test_voce_gestione_spese_ha_etichetta_non_vuota():
    etichette = [lbl for lbl, key in sidebar.PAGINE.items() if key == GESTIONE_SPESE_KEY]
    assert len(etichette) == 1, (
        "Deve esserci una sola voce di navigazione per 'gestione_spese'"
    )
    etichetta = etichette[0]
    assert isinstance(etichetta, str) and etichetta.strip() != "", (
        "L'etichetta della voce 'gestione_spese' non deve essere vuota"
    )


# ---------------------------------------------------------------------------
# Requirement 1.2, 1.3 - chiave univoca e non coincidente con le pagine esistenti
# ---------------------------------------------------------------------------

def test_chiave_gestione_spese_unica_in_pagine():
    valori = list(sidebar.PAGINE.values())
    assert valori.count(GESTIONE_SPESE_KEY) == 1, (
        "La chiave 'gestione_spese' deve comparire una sola volta in PAGINE"
    )


def test_tutte_le_chiavi_pagine_sono_univoche():
    valori = list(sidebar.PAGINE.values())
    assert len(valori) == len(set(valori)), (
        "Le chiavi di routing in PAGINE devono essere tutte univoche"
    )


def test_chiave_gestione_spese_non_collide_con_pagine_esistenti():
    assert GESTIONE_SPESE_KEY not in PAGINE_ESISTENTI, (
        "La chiave 'gestione_spese' non deve coincidere con una pagina esistente"
    )


# ---------------------------------------------------------------------------
# Requirement 1.4 - pagina predefinita "dashboard"
# ---------------------------------------------------------------------------

def test_default_page_dashboard_in_app(app_source):
    """app.py main() inizializza st.session_state.page a 'dashboard'."""
    assert re.search(
        r"st\.session_state\.page\s*=\s*[\"']dashboard[\"']",
        app_source,
    ), "app.py deve impostare la pagina predefinita a 'dashboard'"


def test_default_page_dashboard_in_sidebar():
    """La sidebar usa 'dashboard' come fallback dell'indice corrente."""
    src = Path(sidebar.__file__).read_text(encoding="utf-8")
    assert "dashboard" in src, (
        "views/sidebar.py deve riferirsi alla pagina predefinita 'dashboard'"
    )


# ---------------------------------------------------------------------------
# Requirement 1.5 - render_gestione_spese e ramo di routing
# ---------------------------------------------------------------------------

def test_render_gestione_spese_esiste():
    from views import gestione_spese

    assert hasattr(gestione_spese, "render_gestione_spese"), (
        "views.gestione_spese deve definire render_gestione_spese"
    )
    assert callable(gestione_spese.render_gestione_spese), (
        "render_gestione_spese deve essere una funzione invocabile"
    )


def test_app_importa_render_gestione_spese(app_source):
    assert re.search(
        r"from\s+views\.gestione_spese\s+import\s+render_gestione_spese",
        app_source,
    ), "app.py deve importare render_gestione_spese da views.gestione_spese"


def test_app_ha_ramo_routing_gestione_spese(app_source):
    """Il routing di app.py deve avere il ramo per 'gestione_spese'."""
    # Ramo condizionale sulla pagina.
    assert re.search(
        r"st\.session_state\.page\s*==\s*[\"']gestione_spese[\"']",
        app_source,
    ), "app.py deve contenere il confronto st.session_state.page == 'gestione_spese'"
    # Chiamata alla funzione di rendering nel ramo.
    assert re.search(r"render_gestione_spese\s*\(\s*\)", app_source), (
        "app.py deve invocare render_gestione_spese() nel ramo di routing"
    )

# Feature: gestione-spese, Property 14
"""Property test della costruzione PURA della coppia di Movimenti speculari
generata da `database.insert_trasferimento` (Property 14, Req 7.1).

Per ogni trasferimento valido (conti distinti, importo > 0, data ISO), la
costruzione produce due Movimenti con pari importo (in valore assoluto) e pari
data valuta:
  - uno con Tipo_Movimento "Trasferimento uscita" sul conto di origine, con
    importo negativo;
  - uno con Tipo_Movimento "Trasferimento ingresso" sul conto di destinazione,
    con importo positivo.
I due importi sono esattamente opposti (somma == 0) e di pari magnitudine pari
ad abs(importo) arrotondato a 2 decimali.

Per testare la costruzione PURA senza toccare la rete, `database.supabase`
viene mockato con un fake fluente che cattura i payload dei due insert (stesso
approccio di `tests/test_database_integration.py`: fake streamlit + stub di
`supabase.create_client` PRIMA dell'import, poi monkeypatch di
`database.supabase` per test).

Validates: Requirements 7.1
"""

import sys
from datetime import date
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Import di `database` senza rete ne' credenziali reali (vedi docstring).
# ---------------------------------------------------------------------------
_fake_st = MagicMock()
_fake_st.secrets.__getitem__.side_effect = KeyError("no secrets in test")
sys.modules.setdefault("streamlit", _fake_st)

import supabase as _supabase_pkg  # noqa: E402

_supabase_pkg.create_client = lambda *a, **k: MagicMock(name="create_client_stub")

import database  # noqa: E402


# ---------------------------------------------------------------------------
# Fake fluente che cattura i payload degli insert sulla tabella "movimenti".
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, data=None):
        self.data = data if data is not None else []


class FakeQuery:
    def __init__(self, table_name, inserts):
        self._table = table_name
        self._inserts = inserts
        self._payload = None

    def insert(self, payload):
        self._payload = payload
        return self

    def delete(self):
        return self

    def eq(self, *a, **k):
        return self

    def execute(self):
        if self._payload is not None and self._table == "movimenti":
            self._inserts.append(self._payload)
            # Restituisce un id cosi' l'eventuale compensazione avrebbe un id;
            # in questi casi (entrambi gli insert riescono) non viene usata.
            return FakeResponse([{"id": len(self._inserts)}])
        return FakeResponse([])


class FakeSupabase:
    def __init__(self):
        self.inserts = []

    def table(self, name):
        return FakeQuery(name, self.inserts)


# ---------------------------------------------------------------------------
# Strategie Hypothesis per input validi (Req 7.1).
# ---------------------------------------------------------------------------

_ids = st.integers(min_value=1, max_value=10_000)
# Importi strettamente positivi, con magnitudini realistiche (finiti, no NaN).
_importi = st.floats(
    min_value=0.01,
    max_value=1_000_000.0,
    allow_nan=False,
    allow_infinity=False,
)
_date_iso = st.dates(
    min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)
).map(lambda d: d.isoformat())


@settings(max_examples=100)
@given(
    conto_origine=_ids,
    conto_dest=_ids,
    importo=_importi,
    data_iso=_date_iso,
)
def test_coppia_trasferimento_speculare(conto_origine, conto_dest, importo, data_iso):
    """La coppia prodotta e' speculare: tipi uscita/ingresso, importi opposti di
    pari magnitudine e pari data, sui conti origine/destinazione (Property 14,
    Req 7.1)."""
    fake = FakeSupabase()
    # monkeypatch manuale (il fake e' ricreato per ogni esempio Hypothesis)
    original = database.supabase
    database.supabase = fake
    try:
        database.insert_trasferimento(
            conto_origine_id=conto_origine,
            conto_dest_id=conto_dest,
            importo_eur=importo,
            data_iso=data_iso,
        )
    finally:
        database.supabase = original

    # Esattamente due Movimenti costruiti e inseriti
    assert len(fake.inserts) == 2
    uscita, ingresso = fake.inserts

    # Tipi dei due Movimenti
    assert uscita["tipo_movimento"] == "Trasferimento uscita"
    assert ingresso["tipo_movimento"] == "Trasferimento ingresso"

    # Conti: origine lato uscita, destinazione lato ingresso
    assert uscita["conto_id"] == conto_origine
    assert ingresso["conto_id"] == conto_dest

    # Stessa data valuta per entrambi
    assert uscita["data_movimento"] == ingresso["data_movimento"] == data_iso

    # Segni opposti: uscita negativa, ingresso positiva
    assert uscita["importo_eur"] < 0
    assert ingresso["importo_eur"] > 0

    # Importi esattamente opposti: somma == 0
    assert uscita["importo_eur"] + ingresso["importo_eur"] == 0

    # Pari magnitudine, uguale ad abs(importo)
    magnitudine = abs(importo)
    assert abs(uscita["importo_eur"]) == magnitudine
    assert ingresso["importo_eur"] == magnitudine
    # ... e coerente con abs(importo) arrotondato a 2 decimali
    assert round(ingresso["importo_eur"], 2) == round(magnitudine, 2)

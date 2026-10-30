# Feature: gestione-spese, task 10.7: integration test del layer dati (Supabase mockato)
"""Integration test del layer dati di `database.py` con Supabase MOCKATO.

Questi test NON toccano la rete: il client `database.supabase` viene sostituito
via monkeypatch con un fake fluente che registra le chiamate
(`table().insert()/upsert()/update()/delete().eq().execute()`), cosi' da poter
asserire su tabelle, payload, chiavi di conflitto e flag.

Coprono (1-3 esempi rappresentativi):
- creazione automatica di conti/categorie mancanti (Req 3.5, 3.6);
- rollback per compensazione del trasferimento quando il secondo lato fallisce
  (Req 7.2, 5.6);
- upsert del mapping esercente da correzione, che AGGIORNA la voce esistente
  (Req 6.5, 6.6);
- update/delete di un movimento (Req 8.8, 8.10);
- uso esclusivo di Supabase (via `get_secret`) e gestione di errore/
  irraggiungibilita' del servizio senza crash (Req 9.1, 9.5).

Validates: Requirements 3.5, 3.6, 5.6, 7.2, 6.5, 6.6, 8.8, 8.10, 9.1, 9.5
"""

import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Import di `database` senza toccare la rete ne' richiedere credenziali reali.
#
# `database.py` chiama `create_client(...)` a import-time e usa `st.secrets` /
# env via `get_secret`. Qui mockiamo `streamlit` e `supabase.create_client`
# PRIMA dell'import, in modo che il modulo si carichi con un client fittizio.
# Nei singoli test sostituiamo comunque `database.supabase` con un fake dedicato.
# ---------------------------------------------------------------------------

# streamlit: st.secrets[...] deve sollevare per forzare il fallback su os.getenv
_fake_st = MagicMock()
_fake_st.secrets.__getitem__.side_effect = KeyError("no secrets in test")
sys.modules.setdefault("streamlit", _fake_st)

import supabase as _supabase_pkg  # noqa: E402

_supabase_pkg.create_client = lambda *a, **k: MagicMock(name="create_client_stub")

import database  # noqa: E402


# ---------------------------------------------------------------------------
# Fake fluente del client Supabase che registra le chiamate.
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, data=None):
        self.data = data if data is not None else []


class FakeQuery:
    """Catena fluente che registra l'operazione e i filtri, poi esegue.

    `executor` e' una funzione che riceve l'operazione registrata e ritorna la
    `FakeResponse` (o solleva un'eccezione per simulare un errore Supabase).
    """

    def __init__(self, table_name, calls, executor):
        self._table = table_name
        self._calls = calls
        self._executor = executor
        self._op = {"table": table_name, "method": None, "payload": None,
                    "kwargs": {}, "eq": []}

    def insert(self, payload):
        self._op["method"] = "insert"
        self._op["payload"] = payload
        return self

    def upsert(self, payload, **kwargs):
        self._op["method"] = "upsert"
        self._op["payload"] = payload
        self._op["kwargs"] = kwargs
        return self

    def update(self, payload):
        self._op["method"] = "update"
        self._op["payload"] = payload
        return self

    def delete(self):
        self._op["method"] = "delete"
        return self

    def select(self, *a, **k):
        self._op["method"] = self._op["method"] or "select"
        return self

    def eq(self, col, val):
        self._op["eq"].append((col, val))
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def range(self, *a, **k):
        return self

    def execute(self):
        self._calls.append(self._op)
        return self._executor(self._op)


class FakeSupabase:
    """Fake del client: `.table(name)` restituisce una FakeQuery e registra
    tutte le operazioni eseguite in `self.calls`."""

    def __init__(self, executor=None):
        self.calls = []
        # default executor: ritorna una risposta vuota
        self._executor = executor or (lambda op: FakeResponse([]))

    def table(self, name):
        return FakeQuery(name, self.calls, self._executor)

    def ops(self, method=None, table=None):
        """Filtra le operazioni registrate per metodo/tabella."""
        return [
            c for c in self.calls
            if (method is None or c["method"] == method)
            and (table is None or c["table"] == table)
        ]


@pytest.fixture
def fake_supabase(monkeypatch):
    """Installa un FakeSupabase su `database.supabase` e lo restituisce."""
    fake = FakeSupabase()
    monkeypatch.setattr(database, "supabase", fake)
    return fake


# ---------------------------------------------------------------------------
# Req 3.5 / 3.6 - creazione automatica di conti e categorie mancanti
# ---------------------------------------------------------------------------

def test_get_or_create_conto_crea_conto_mancante_e_ritorna_id(monkeypatch):
    """get_or_create_conto fa l'upsert idempotente del conto e ritorna l'id
    letto subito dopo (Req 3.5)."""
    def executor(op):
        if op["method"] == "upsert" and op["table"] == "conti":
            return FakeResponse([])  # upsert idempotente, nessun dato restituito
        if op["method"] == "select" and op["table"] == "conti":
            return FakeResponse([{"id": 42}])  # lettura dell'id appena creato
        return FakeResponse([])

    fake = FakeSupabase(executor)
    monkeypatch.setattr(database, "supabase", fake)

    conto_id = database.get_or_create_conto("BBVA")

    assert conto_id == 42
    # Ha eseguito l'upsert idempotente sul conto mancante
    upserts = fake.ops(method="upsert", table="conti")
    assert len(upserts) == 1
    assert upserts[0]["payload"] == {"nome": "BBVA"}
    assert upserts[0]["kwargs"]["on_conflict"] == "nome"
    assert upserts[0]["kwargs"]["ignore_duplicates"] is True


def test_upsert_categoria_e_sotto_categoria_per_mancanti(fake_supabase):
    """upsert_categoria/upsert_sotto_categoria creano le voci mancanti con le
    chiavi di conflitto attese (Req 3.6)."""
    database.upsert_categoria("Spesa alimentare")
    database.upsert_sotto_categoria("Supermercato", categoria_id=7)

    cat = fake_supabase.ops(method="upsert", table="categorie")
    assert len(cat) == 1
    assert cat[0]["payload"] == {"nome": "Spesa alimentare"}
    assert cat[0]["kwargs"]["on_conflict"] == "nome"
    assert cat[0]["kwargs"]["ignore_duplicates"] is True

    sot = fake_supabase.ops(method="upsert", table="sotto_categorie")
    assert len(sot) == 1
    assert sot[0]["payload"] == {"nome": "Supermercato", "categoria_id": 7}
    assert sot[0]["kwargs"]["on_conflict"] == "categoria_id, nome"
    assert sot[0]["kwargs"]["ignore_duplicates"] is True


# ---------------------------------------------------------------------------
# Req 7.2 / 5.6 - rollback per compensazione del trasferimento
# ---------------------------------------------------------------------------

def test_insert_trasferimento_rollback_se_secondo_lato_fallisce(monkeypatch):
    """Se l'inserimento del lato ingresso fallisce, il lato uscita gia' creato
    viene eliminato (compensazione) e la funzione ritorna None (Req 7.2, 5.6)."""
    state = {"inserts": 0}

    def executor(op):
        if op["method"] == "insert" and op["table"] == "movimenti":
            state["inserts"] += 1
            if state["inserts"] == 1:
                # lato uscita: inserito con id noto
                return FakeResponse([{"id": 101}])
            # lato ingresso: il servizio fallisce
            raise RuntimeError("insert ingresso fallito")
        if op["method"] == "delete" and op["table"] == "movimenti":
            return FakeResponse([{"id": 101}])
        return FakeResponse([])

    fake = FakeSupabase(executor)
    monkeypatch.setattr(database, "supabase", fake)

    res = database.insert_trasferimento(
        conto_origine_id=1,
        conto_dest_id=2,
        importo_eur=50.0,
        data_iso="2024-03-01",
    )

    # Nessun risultato: trasferimento non completato
    assert res is None
    # Due insert tentati (uscita + ingresso)
    assert len(fake.ops(method="insert", table="movimenti")) == 2
    # Compensazione: il lato uscita (id=101) e' stato eliminato
    deletes = fake.ops(method="delete", table="movimenti")
    assert len(deletes) == 1
    assert ("id", 101) in deletes[0]["eq"]


# ---------------------------------------------------------------------------
# Req 6.5 / 6.6 - upsert del mapping esercente da correzione (AGGIORNA)
# ---------------------------------------------------------------------------

def test_upsert_mapping_esercente_aggiorna_voce_esistente(fake_supabase):
    """upsert_mapping_esercente usa on_conflict=esercente_normalizzato con
    ignore_duplicates=False: una correzione aggiorna la voce esistente
    (Req 6.5 nuova voce, Req 6.6 correzione)."""
    database.upsert_mapping_esercente("esselunga", categoria_id=3, sotto_categoria_id=9)

    ups = fake_supabase.ops(method="upsert", table="mapping_esercente_categoria")
    assert len(ups) == 1
    assert ups[0]["payload"] == {
        "esercente_normalizzato": "esselunga",
        "categoria_id": 3,
        "sotto_categoria_id": 9,
    }
    assert ups[0]["kwargs"]["on_conflict"] == "esercente_normalizzato"
    # ignore_duplicates=False => in caso di conflitto la riga viene aggiornata
    assert ups[0]["kwargs"]["ignore_duplicates"] is False


# ---------------------------------------------------------------------------
# Req 8.8 / 8.10 - update e delete di un movimento
# ---------------------------------------------------------------------------

def test_update_e_delete_movimento_emettono_le_chiamate_corrette(fake_supabase):
    """update_movimento fa update(...).eq('id', ...); delete_movimento fa
    delete().eq('id', ...) sulla tabella movimenti (Req 8.8, 8.10)."""
    database.update_movimento(55, {"categoria_id": 4, "nota": "corretto"})
    database.delete_movimento(55)

    updates = fake_supabase.ops(method="update", table="movimenti")
    assert len(updates) == 1
    assert updates[0]["payload"] == {"categoria_id": 4, "nota": "corretto"}
    assert ("id", 55) in updates[0]["eq"]

    deletes = fake_supabase.ops(method="delete", table="movimenti")
    assert len(deletes) == 1
    assert ("id", 55) in deletes[0]["eq"]


# ---------------------------------------------------------------------------
# Req 9.1 / 9.5 - uso esclusivo di Supabase e gestione errori senza crash
# ---------------------------------------------------------------------------

def test_funzioni_non_crashano_quando_supabase_irraggiungibile(monkeypatch):
    """Se Supabase e' irraggiungibile (ogni execute solleva), le funzioni del
    layer dati loggano e ritornano un valore neutro senza propagare l'errore
    (Req 9.1 Supabase unica sorgente, Req 9.5 nessun crash)."""
    def executor(op):
        raise ConnectionError("servizio Supabase irraggiungibile")

    fake = FakeSupabase(executor)
    monkeypatch.setattr(database, "supabase", fake)

    # Letture -> lista vuota, nessuna eccezione
    assert database.get_conti() == []
    assert database.get_categorie() == []
    assert database.get_mapping_esercente() == []
    assert database.get_movimenti() == []

    # Scritture -> None, nessuna eccezione
    assert database.upsert_conto("X") is None
    assert database.upsert_categoria("Y") is None
    assert database.upsert_mapping_esercente("z", 1, None) is None
    assert database.update_movimento(1, {"nota": "x"}) is None
    assert database.delete_movimento(1) is None
    assert database.get_or_create_conto("X") is None
    # Il trasferimento fallisce al primo insert -> None (nessuna compensazione)
    assert database.insert_trasferimento(1, 2, 10.0, "2024-01-01") is None


def test_get_secret_usa_env_quando_streamlit_assente(monkeypatch):
    """get_secret ricade su os.getenv quando st.secrets non ha la chiave,
    confermando che le credenziali Supabase arrivano via get_secret (Req 9.1)."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    assert database.get_secret("SUPABASE_URL") == "https://example.supabase.co"
    # chiave assente -> default
    assert database.get_secret("CHIAVE_INESISTENTE_XYZ", "fallback") == "fallback"

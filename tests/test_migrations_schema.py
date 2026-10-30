# Feature: gestione-spese
"""Smoke test dello schema delle migrazioni SQL Supabase (task 2.6).

Verifica, tramite parsing statico del testo SQL, che le 5 migrazioni
timestamp-prefixed esistano e dichiarino le colonne, i vincoli NOT NULL,
UNIQUE, CHECK e le FK attese dal design.

Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.7, 2.8, 2.10, 6.1
"""

import re
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "supabase" / "migrations"

# Mappa: nome logico tabella -> nome file migrazione atteso (timestamp-prefixed)
MIGRATION_FILES = {
    "conti": "20250101000001_create_conti_table.sql",
    "categorie": "20250101000002_create_categorie_table.sql",
    "sotto_categorie": "20250101000003_create_sotto_categorie_table.sql",
    "movimenti": "20250101000004_create_movimenti_table.sql",
    "mapping_esercente_categoria": "20250101000005_create_mapping_esercente_categoria_table.sql",
}

TIPO_MOVIMENTO_VALUES = [
    "Spese",
    "In",
    "Trasferimento ingresso",
    "Trasferimento uscita",
    "Aumento Saldo",
    "Decremento Saldo",
]


def _normalize_sql(text):
    """Collassa gli spazi bianchi (inclusi i newline) in spazi singoli, lowercase."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _read_migration(table_name):
    path = MIGRATIONS_DIR / MIGRATION_FILES[table_name]
    return path.read_text(encoding="utf-8")


def _column_regex(column, column_type):
    """Regex per una dichiarazione di colonna: `<col> <type>`."""
    return re.compile(rf"\b{re.escape(column)}\s+{re.escape(column_type)}\b", re.IGNORECASE)


def _not_null_regex(column, column_type):
    """Regex per una colonna dichiarata NOT NULL.

    Consente opzioni intermedie fra il tipo e `not null` (es. `references ...`),
    ma si ferma prima di una virgola o parentesi di chiusura.
    """
    return re.compile(
        rf"\b{re.escape(column)}\s+{re.escape(column_type)}\b[^,()]*?\bnot\s+null\b",
        re.IGNORECASE,
    )


def _fk_regex(column):
    """Regex per una colonna con un vincolo FK `references ...`."""
    return re.compile(
        rf"\b{re.escape(column)}\b[^,()]*?\breferences\s+(?:public\.)?(\w+)\s*\(\s*id\s*\)",
        re.IGNORECASE,
    )


# ---------------------------------------------------------------------------
# Presenza dei file timestamp-prefixed (Requirements 2.10)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("table_name,file_name", list(MIGRATION_FILES.items()))
def test_migration_file_exists_and_timestamp_prefixed(table_name, file_name):
    path = MIGRATIONS_DIR / file_name
    assert path.is_file(), f"File di migrazione mancante: {file_name}"
    # Prefisso timestamp: 14 cifre + underscore
    assert re.match(r"^\d{14}_", file_name), (
        f"Il file {file_name} non ha il prefisso timestamp atteso"
    )


@pytest.mark.parametrize("table_name,file_name", list(MIGRATION_FILES.items()))
def test_migration_creates_expected_table(table_name, file_name):
    sql = _normalize_sql(_read_migration(table_name))
    pattern = re.compile(
        rf"create table if not exists (?:public\.)?{re.escape(table_name)}\b"
    )
    assert pattern.search(sql), (
        f"La migrazione {file_name} non crea la tabella attesa '{table_name}'"
    )


# ---------------------------------------------------------------------------
# Tabella conti (Requirements 2.2, 2.10)
# ---------------------------------------------------------------------------

def test_conti_schema():
    sql = _read_migration("conti")
    # Colonna id identity PK
    assert re.search(
        r"id\s+bigint\s+generated\s+always\s+as\s+identity\s+primary\s+key",
        sql,
        re.IGNORECASE,
    ), "conti: manca 'id bigint generated always as identity primary key'"
    # nome varchar not null
    assert _not_null_regex("nome", "varchar").search(sql), "conti: 'nome' deve essere NOT NULL"
    # UNIQUE conti_nome_key
    assert re.search(r"conti_nome_key\s+unique\s*\(\s*nome\s*\)", sql, re.IGNORECASE), (
        "conti: manca il vincolo UNIQUE 'conti_nome_key' su (nome)"
    )
    # CHECK lunghezza > 0
    assert re.search(r"check\s*\(\s*length\s*\(\s*trim\s*\(\s*nome\s*\)\s*\)\s*>\s*0\s*\)", sql, re.IGNORECASE), (
        "conti: manca il CHECK sulla lunghezza di nome > 0"
    )


# ---------------------------------------------------------------------------
# Tabella categorie (Requirements 2.3, 2.10)
# ---------------------------------------------------------------------------

def test_categorie_schema():
    sql = _read_migration("categorie")
    assert _not_null_regex("nome", "varchar").search(sql), "categorie: 'nome' deve essere NOT NULL"
    assert re.search(r"categorie_nome_key\s+unique\s*\(\s*nome\s*\)", sql, re.IGNORECASE), (
        "categorie: manca il vincolo UNIQUE 'categorie_nome_key' su (nome)"
    )
    assert re.search(r"check\s*\(\s*length\s*\(\s*trim\s*\(\s*nome\s*\)\s*\)\s*>\s*0\s*\)", sql, re.IGNORECASE), (
        "categorie: manca il CHECK sulla lunghezza di nome > 0"
    )


# ---------------------------------------------------------------------------
# Tabella sotto_categorie (Requirements 2.4, 2.10)
# ---------------------------------------------------------------------------

def test_sotto_categorie_schema():
    sql = _read_migration("sotto_categorie")
    # categoria_id bigint not null references categorie(id)
    assert _not_null_regex("categoria_id", "bigint").search(sql), (
        "sotto_categorie: 'categoria_id' deve essere NOT NULL"
    )
    fk = _fk_regex("categoria_id").search(sql)
    assert fk and fk.group(1).lower() == "categorie", (
        "sotto_categorie: 'categoria_id' deve referenziare categorie(id)"
    )
    # nome varchar not null
    assert _not_null_regex("nome", "varchar").search(sql), "sotto_categorie: 'nome' deve essere NOT NULL"
    # UNIQUE su (categoria_id, nome)
    assert re.search(
        r"sotto_categorie_cat_nome_key\s+unique\s*\(\s*categoria_id\s*,\s*nome\s*\)",
        sql,
        re.IGNORECASE,
    ), "sotto_categorie: manca UNIQUE 'sotto_categorie_cat_nome_key' su (categoria_id, nome)"
    # CHECK lunghezza > 0
    assert re.search(r"check\s*\(\s*length\s*\(\s*trim\s*\(\s*nome\s*\)\s*\)\s*>\s*0\s*\)", sql, re.IGNORECASE), (
        "sotto_categorie: manca il CHECK sulla lunghezza di nome > 0"
    )


# ---------------------------------------------------------------------------
# Tabella movimenti (Requirements 2.1, 2.7, 2.8, 2.10)
# ---------------------------------------------------------------------------

def test_movimenti_required_columns_not_null():
    sql = _read_migration("movimenti")
    required = {
        "data_movimento": "date",
        "conto_id": "bigint",
        "importo_eur": "numeric",
        "tipo_movimento": "varchar",
        "valuta": "varchar",
        "descrizione_normalizzata": "varchar",
    }
    for column, col_type in required.items():
        assert _not_null_regex(column, col_type).search(sql), (
            f"movimenti: la colonna obbligatoria '{column} {col_type}' deve essere NOT NULL"
        )


def test_movimenti_optional_columns_present():
    sql = _read_migration("movimenti")
    for column, col_type in {
        "categoria_id": "bigint",
        "sotto_categoria_id": "bigint",
        "nota": "varchar",
        "descrizione": "varchar",
    }.items():
        assert _column_regex(column, col_type).search(sql), (
            f"movimenti: manca la colonna facoltativa '{column} {col_type}'"
        )


def test_movimenti_foreign_keys():
    sql = _read_migration("movimenti")
    conto_fk = _fk_regex("conto_id").search(sql)
    assert conto_fk and conto_fk.group(1).lower() == "conti", (
        "movimenti: 'conto_id' deve referenziare conti(id)"
    )
    categoria_fk = _fk_regex("categoria_id").search(sql)
    assert categoria_fk and categoria_fk.group(1).lower() == "categorie", (
        "movimenti: 'categoria_id' deve referenziare categorie(id)"
    )
    sotto_fk = _fk_regex("sotto_categoria_id").search(sql)
    assert sotto_fk and sotto_fk.group(1).lower() == "sotto_categorie", (
        "movimenti: 'sotto_categoria_id' deve referenziare sotto_categorie(id)"
    )


def test_movimenti_tipo_movimento_check():
    sql = _normalize_sql(_read_migration("movimenti"))
    assert "movimenti_tipo_movimento_check" in sql, (
        "movimenti: manca il vincolo CHECK 'movimenti_tipo_movimento_check'"
    )
    # Estrae il blocco `in ( ... )` del tipo_movimento e verifica i valori attesi
    for value in TIPO_MOVIMENTO_VALUES:
        assert f"'{value.lower()}'" in sql, (
            f"movimenti: il CHECK su tipo_movimento deve includere il valore '{value}'"
        )
    # Verifica che il CHECK sia proprio su tipo_movimento in (...)
    assert re.search(r"tipo_movimento\s+in\s*\(", sql), (
        "movimenti: il CHECK deve essere nella forma 'tipo_movimento in (...)'"
    )


def test_movimenti_chiave_naturale_unique():
    sql = _normalize_sql(_read_migration("movimenti"))
    assert re.search(
        r"movimenti_chiave_naturale_key\s+unique\s*\(\s*data_movimento\s*,\s*conto_id\s*,\s*importo_eur\s*,\s*descrizione_normalizzata\s*\)",
        sql,
    ), (
        "movimenti: manca UNIQUE 'movimenti_chiave_naturale_key' su "
        "(data_movimento, conto_id, importo_eur, descrizione_normalizzata)"
    )


def test_movimenti_valuta_default_eur():
    sql = _read_migration("movimenti")
    assert re.search(r"valuta\s+varchar\s+not\s+null\s+default\s+'eur'", sql, re.IGNORECASE), (
        "movimenti: 'valuta' deve avere default 'EUR'"
    )


# ---------------------------------------------------------------------------
# Tabella mapping_esercente_categoria (Requirements 6.1, 2.10)
# ---------------------------------------------------------------------------

def test_mapping_esercente_schema():
    sql = _read_migration("mapping_esercente_categoria")
    # esercente_normalizzato varchar not null
    assert _not_null_regex("esercente_normalizzato", "varchar").search(sql), (
        "mapping: 'esercente_normalizzato' deve essere NOT NULL"
    )
    # UNIQUE mapping_esercente_key su (esercente_normalizzato)
    assert re.search(
        r"mapping_esercente_key\s+unique\s*\(\s*esercente_normalizzato\s*\)",
        sql,
        re.IGNORECASE,
    ), "mapping: manca UNIQUE 'mapping_esercente_key' su (esercente_normalizzato)"
    # categoria_id bigint not null references categorie(id)
    assert _not_null_regex("categoria_id", "bigint").search(sql), (
        "mapping: 'categoria_id' deve essere NOT NULL"
    )
    categoria_fk = _fk_regex("categoria_id").search(sql)
    assert categoria_fk and categoria_fk.group(1).lower() == "categorie", (
        "mapping: 'categoria_id' deve referenziare categorie(id)"
    )
    # sotto_categoria_id bigint references sotto_categorie(id) (facoltativo)
    sotto_fk = _fk_regex("sotto_categoria_id").search(sql)
    assert sotto_fk and sotto_fk.group(1).lower() == "sotto_categorie", (
        "mapping: 'sotto_categoria_id' deve referenziare sotto_categorie(id)"
    )

from datetime import datetime

def format_currency(value, symbol="€"):
    return f"{symbol}{value:,.2f}"

def validate_isin(isin):
    return isinstance(isin, str) and len(isin) == 12

def format_date(date, fmt="%d/%m/%Y"):
    return date.strftime(fmt)

def normalize_data(data_input):
    
    # 1. Converti la stringa in un oggetto datetime
    data_obj = datetime.strptime(data_input, "%d-%m-%Y")
    # 2. Riconverto in stringa nel formato ISO (YYYY-MM-DD) accettato da Supabase
    data_iso = data_obj.strftime("%Y-%m-%d") # Risultato: "2025-11-17"
    
    return data_iso

from unidecode import unidecode

# Supponiamo tu abbia caricato il df
# df = pd.read_csv(...) o df = pd.read_excel(...)

# 1. Funzione per pulire le stringhe (es. "Quantità  " -> "quantita")
def clean_col_name(name):
    # Rimuove accenti, spazi, caratteri strani e mette tutto minuscolo
    return unidecode(str(name)).lower().strip().replace(" ", "_").replace("-", "_")


def _to_iso(value):
    """Converte una data (Timestamp/datetime/str) in stringa ISO YYYY-MM-DD.

    Ritorna None se il valore non e' valorizzato."""
    import pandas as pd
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    # Timestamp / datetime
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    # Stringa gia' in formato dd-mm-yyyy
    try:
        return normalize_data(str(value))
    except Exception:
        try:
            return pd.to_datetime(value, dayfirst=True).strftime("%Y-%m-%d")
        except Exception:
            return None


def extract_bond_coupons(df):
    """Estrae le cedole obbligazionarie da un DataFrame di movimenti Directa.

    Il DataFrame deve avere i nomi colonna gia' normalizzati con clean_col_name
    (es. 'data_operazione', 'tipo_operazione', 'ticker', 'isin', 'descrizione',
    'importo_euro', 'protocollo', 'data_valuta').

    Abbina ogni riga 'Cedola obb.' (importo lordo positivo) con l'eventuale
    'Rit.cedola obb.' dello stesso ISIN e stessa data operazione (ritenuta
    negativa), calcolando l'importo netto.

    Ritorna:
        list[dict]: record pronti per database.insert_bond_coupons.
    """
    import pandas as pd

    if df is None or len(df) == 0:
        return []

    cols = set(df.columns)
    required = {"tipo_operazione", "importo_euro", "data_operazione"}
    if not required.issubset(cols):
        return []

    def _tipo(row):
        return str(row.get("tipo_operazione", "")).strip().lower()

    cedole = df[df["tipo_operazione"].astype(str).str.strip().str.lower() == "cedola obb."].copy()
    ritenute = df[df["tipo_operazione"].astype(str).str.strip().str.lower() == "rit.cedola obb."].copy()

    if cedole.empty:
        return []

    # Indicizza le ritenute per (isin, data_operazione) per un abbinamento rapido
    def _key(row):
        isin = str(row.get("isin", "") or "").strip()
        data = _to_iso(row.get("data_operazione"))
        return (isin, data)

    rit_map = {}
    for _, r in ritenute.iterrows():
        rit_map[_key(r)] = r

    records = []
    for _, c in cedole.iterrows():
        isin = str(c.get("isin", "") or "").strip()
        data_iso = _to_iso(c.get("data_operazione"))
        lordo = float(c.get("importo_euro") or 0)

        r = rit_map.get((isin, data_iso))
        ritenuta = abs(float(r.get("importo_euro") or 0)) if r is not None else 0.0
        netto = round(lordo - ritenuta, 2)

        protocollo_cedola = str(c.get("protocollo", "") or "").strip()
        if not protocollo_cedola:
            # Fallback: costruisci una chiave stabile se manca il protocollo
            protocollo_cedola = f"{isin}_{data_iso}_cedola"
        protocollo_ritenuta = (
            str(r.get("protocollo", "") or "").strip() if r is not None else None
        )

        records.append({
            "ticker": str(c.get("ticker", "") or "").strip(),
            "isin": isin or None,
            "descrizione": str(c.get("descrizione", "") or "").strip() or None,
            "data_operazione": data_iso,
            "data_valuta": _to_iso(c.get("data_valuta")) if "data_valuta" in cols else None,
            "importo_lordo_eur": round(lordo, 2),
            "ritenuta_eur": round(ritenuta, 2),
            "importo_netto_eur": netto,
            "protocollo_cedola": protocollo_cedola,
            "protocollo_ritenuta": protocollo_ritenuta,
        })

    return records

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
import os
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Carica le variabili dal file .env
load_dotenv() 
# Reference Supabase: https://supabase.com/docs/reference/python/eq

url: str = os.getenv("SUPABASE_URL","")
key: str = os.getenv("SUPABASE_KEY","")
supabase: Client = create_client(supabase_url=url, supabase_key=key)
'''
# Esempio SELECT
response = (
    supabase.table("etf_data")
    .select("*")
    .execute()
)

print(response)

# Esempio INSERT
response = (
    supabase.table("etf_data")
    .insert({"id": 1, "name": "Pluto"})
    .execute()
)

# Esempio UPDATE
response = (
    supabase.table("instruments")
    .update({"name": "piano"})
    .eq("id", 1)
    .execute()
)
# Esempio DELETE
response = (
    supabase.table("countries")
    .delete()
    .eq("id", 1)
    .execute()
)
'''
# Funzione per inserire una lista di holding nel database
def insert_holdings(etf_ticker, holdings):
    """
    Inserisce una lista di holding per un ETF nel database Supabase.
    Parametri:
        etf_ticker (str): Il ticker dell'ETF di riferimento
        holdings (list of dict): Lista di holding, ogni dict deve avere le chiavi:
            Ticker, Nome, Settore, Asset Class, Valore di mercato, Ponderazione (%),
            Valore nozionale, Nominale, Prezzo, Area Geografica, Cambio, Valuta di mercato
    """
    results = []
    for row in holdings:
        data = {
            "etf_ticker": etf_ticker,
            "ticker": row.get("Ticker"),
            "nome": row.get("Nome"),
            "settore": row.get("Settore"),
            "asset_class": row.get("Asset Class"),
            "valore_mercato": row.get("Valore di mercato"),
            "ponderazione": row.get("Ponderazione (%)"),
            "valore_nozionale": row.get("Valore nozionale"),
            "nominale": row.get("Nominale"),
            "prezzo": row.get("Prezzo"),
            "area_geografica": row.get("Area Geografica"),
            "cambio": row.get("Cambio"),
            "valuta_mercato": row.get("Valuta di mercato")
        }
        res = supabase.table("etf_holdings").insert(data).execute()
        results.append(res)
    return results

# Test della funzione di inserimento dati ETF holdings
if __name__ == "__main__":
    test_etf_ticker = "VWCE"
    test_holdings = [
        {
            "Ticker": "AAPL",
            "Nome": "Apple Inc.",
            "Settore": "Tecnologia",
            "Asset Class": "Azione",
            "Valore di mercato": 1000000,
            "Ponderazione (%)": 5.2,
            "Valore nozionale": 52000,
            "Nominale": 300,
            "Prezzo": 173.5,
            "Area Geografica": "USA",
            "Cambio": 1.0,
            "Valuta di mercato": "USD"
        },
        {
            "Ticker": "MSFT",
            "Nome": "Microsoft Corp.",
            "Settore": "Tecnologia",
            "Asset Class": "Azione",
            "Valore di mercato": 800000,
            "Ponderazione (%)": 4.1,
            "Valore nozionale": 32800,
            "Nominale": 200,
            "Prezzo": 164.0,
            "Area Geografica": "USA",
            "Cambio": 1.0,
            "Valuta di mercato": "USD"
        }
    ]
    print("Test inserimento holdings su etf_holdings...")
    insert_results = insert_holdings(test_etf_ticker, test_holdings)
    for res in insert_results:
        print(res)
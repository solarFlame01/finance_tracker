import os
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import logging
import pandas as pd
from utils import normalize_data
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

def insert_directa_transaction(transaction_data):
    """
    Inserisce una transazione nel database Supabase.
    Parametri:
        transaction_data (dict): Dizionario con le chiavi:
            Data operazione, Data valuta, Tipo operazione, Ticker, Isin, 
            Protocollo, Descrizione, Quantità, Importo euro, Importo Divisa, 
            Divisa, Riferimento ordine
    Ritorna:
        response: Risultato dell'operazione di insert
    """
    batch_data = []

    for row in transaction_data:
        data = {
            "data_operazione": normalize_data(row.get("data_operazione")),
            "data_valuta": normalize_data(row.get("data_valuta")),
            "tipo_operazione": row.get("tipo_operazione"),
            "ticker": row.get("ticker"),
            "isin": row.get("isin"),
            "protocollo": row.get("protocollo"),
            "descrizione": row.get("descrizione"),
            "quantita": row.get("quantita"),
            "importo_euro": row.get("importo_euro"),
            "importo_divisa": row.get("importo_divisa"),
            "divisa": row.get("divisa"),
            "riferimento_ordine": row.get("riferimento_ordine")
        }
        batch_data.append(data)

    # Esegui l'UPSERT in un'unica chiamata fuori dal ciclo
    if batch_data:
        try:
            # on_conflict: indica la colonna (o le colonne) che devono essere uniche.
            # ignore_duplicates=True: se trova un conflitto, NON aggiorna e NON dà errore, semplicemente ignora la riga.
            response = supabase.table("transaction").upsert(
                batch_data, 
                on_conflict="ticker, data_operazione, riferimento_ordine, protocollo",
                ignore_duplicates=True
            ).execute()
                 
        except Exception as e:
            print(f"Errore durante l'upsert: {e}")
            
        results = response
    return results


def get_valid_value(value, default='-'):
    """Controlla che il valore non sia None o nan"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    return value

def get_numeric_value(value, default=0.0):
    """Controlla e converte valore numerico, gestendo nan"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return float(value.replace(",", "."))
    return default

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
    # Cerco se esistono già dati per questo etf_ticker e li elim
    response = (
        supabase.table("etf_holdings")
        .select("*")
        .eq("etf_ticker", etf_ticker)
        .execute()
    )
    if len(response.data) > 0:
        #Se esiste li elimino tutti prima di reinserirli
        print("Dati holdings trovati, procedo con la cancellazione per poi reinserirli.")
        response = (
            supabase.table("etf_holdings")
            .delete()
            .eq("etf_ticker", etf_ticker)
            .execute()
        )
    else:
        print("Nessun dato trovato, procediamo con l'inserimento.")
    
    results = []
    for row in holdings:
        data = {
           "etf_ticker": etf_ticker,
            "ticker": get_valid_value(row.get("Ticker dell'emittente"), etf_ticker),
            "nome": get_valid_value(row.get("Nome")),
            "settore": get_valid_value(row.get("Settore")),
            "asset_class": get_valid_value(row.get("Asset Class")),
            "ponderazione": get_numeric_value(row.get("Ponderazione (%)"), None),
            "area_geografica": get_valid_value(row.get("Area Geografica")),
            "cambio": get_valid_value(row.get("Cambio"), 'EUR'),
            "valuta_mercato": get_valid_value(row.get("Valuta di mercato"))
        }

        res = supabase.table("etf_holdings").insert(data).execute()
        results.append(res)
    return results

def get_portfolio_kpi_etf():
    """
    Recupera le KPI del portafoglio ETF dal database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti le KPI del portafoglio ETF
    """
    try:
        response = supabase.table("v_portfolio_ticker_kpi").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero delle KPI del portafoglio ETF: {e}")
        return []

def get_etf_list():
    """
    Recupera tutti i ticker distinti dalla tabella "etf_holdings" nel database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti i ticker degli ETF
    """
    try:
        response = supabase.table("unique_tickers_view").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero della lista ETF: {e}")
        return []
    
def get_etf_transaction_updated():
    """
    Recupera tutte le transazioni con i relativi prezzi aggiornati e le % di crescita per singola transazione
    
    Ritorna:
        list: Lista di dizionari contenenti ETF e dettagli di transazione
    """
    try:
        response = supabase.table("etf_transaction_updated").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero della lista ETF: {e}")
        return []

def get_top_3_etf():
    """
    Recupera i 3 ETF con le migliori performance dal database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti i top 3 ETF
    """
    try:
        response = supabase.table("v_top_3_etf_guadagni").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero dei top 3 ETF: {e}")
        return []

def get_bottom_3_etf():
    """
    Recupera i 3 ETF con le peggiori performance dal database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti i bottom 3 ETF
    """
    try:
        response = supabase.table("v_bottom_3_etf_guadagni").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero dei bottom 3 ETF: {e}")
        return [] 
def get_distribuzione_etf():
    """
    Recupera la distribuzione del portafoglio per ETF dal database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti la distribuzione per ETF
    """
    try:
        response = supabase.table("v_dist_etf").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero della distribuzione ETF: {e}")
        return []

def get_distribuzione_settore():
    """
    Recupera la distribuzione del portafoglio per settore dal database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti la distribuzione per settore
    """
    try:
        response = supabase.table("v_dist_settore").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero della distribuzione settore: {e}")
        return []

def get_distribuzione_valuta_mercato():
    """
    Recupera la distribuzione del portafoglio per valuta di mercato dal database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti la distribuzione per valuta di mercato
    """
    try:
        response = supabase.table("v_dist_valuta_mercato").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero della distribuzione valuta mercato: {e}")
        return []

def get_distribuzione_area_geografica():
    """
    Recupera la distribuzione del portafoglio per area geografica dal database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti la distribuzione per area geografica
    """
    try:
        response = supabase.table("v_dist_area_geografica").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero della distribuzione area geografica: {e}")
        return []  
    
def get_prezzo_medio_acquisto():
    """
    Recupera il prezzo medio di acquisto per ETF dal database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti il prezzo medio di acquisto per ETF
    """
    try:
        response = supabase.table("v_portfolio_positions").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero del prezzo medio di acquisto: {e}")
        return []   
      
def insert_update_etf_price(ticker, price):
    """
    Inserisce o aggiorna il prezzo di un ETF nella tabella "etf_prices".
    
    Parametri:
        ticker (str): Il ticker dell'ETF
        price (float): Il prezzo corrente dell'ETF
    Ritorna:
        response: Risultato dell'operazione di insert/update
    """
    try:
        data = {
            "ticker": ticker,
            "price": price
        }
        response = supabase.table("etf_prices").upsert(
            data, 
            on_conflict="ticker"
        ).execute()
        return response
    except Exception as e:
        logging.error(f"Errore durante l'inserimento/aggiornamento del prezzo per {ticker}: {e}")
        return None
    
def insert_etf_history(history_df):
    """
    Inserisce lo storico dei prezzi di un ETF nella tabella "etf_price_history".
    
    Parametri:
        ticker (str): Il ticker dell'ETF
        history_df (DataFrame): DataFrame contenente lo storico dei prezzi con colonne 'date' e 'close'
    Ritorna:
        response: Risultato dell'operazione di insert
    """
    try:
        batch_data = []
        for _, row in history_df.iterrows():
            data = {
                "ticker": row['ticker'],
                "date": row['date'].strftime("%Y-%m-%d"),
                "close": row['close']
            }
            batch_data.append(data)
        
        if batch_data:
            response = supabase.table("etf_price_history").upsert(
                batch_data, 
                on_conflict="ticker, date, close"
            ).execute()
            return response
    except Exception as e:
        logging.error(f"Errore durante l'inserimento dello storico")
        return None
def insert_update_etf_transaction(nuova_transazione):
    """
    Inserisce o aggiorna il prezzo
    """
    try:
        response = supabase.table("transaction").upsert(
        nuova_transazione, 
            on_conflict="data_operazione, ticker, riferimento_ordine, protocollo"
        ).execute()
        return response
    except Exception as e:
        logging.error(f"Errore durante l'inserimento/aggiornamento del prezzo")
        return None

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
    #insert_results = insert_holdings(test_etf_ticker, test_holdings)
    response = (
        supabase.table("etf_holdings")
        .select("*")
        .eq("etf_ticker", "CSPX")
        .execute()
    )
    if len(response.data) > 0:
        print("Dati holdings trovati:")
        response = (
            supabase.table("etf_holdings")
            .delete()
            .eq("etf_ticker", "CSPX")
            .execute()
        )
    else:
        print("Nessun dato trovato.")


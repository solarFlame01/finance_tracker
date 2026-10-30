import os
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import logging
import pandas as pd
import streamlit as st
from utils import normalize_data
# Carica le variabili dal file .env
load_dotenv() 

# Funzione helper per recuperare secrets in modo sicuro
def get_secret(key: str, default: str = "") -> str:
    """
    Recupera il secret prima da Streamlit secrets poi da environment variables
    """
    try:
        # Prova prima st.secrets (Streamlit Cloud o .streamlit/secrets.toml locale)
        return st.secrets[key]
    except (FileNotFoundError, KeyError):
        # Fallback su environment variables (locale con .env)
        return os.getenv(key, default)

# Recupera le credenziali
url: str = get_secret("SUPABASE_URL")
key: str = get_secret("SUPABASE_KEY")

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
            "data_operazione": (row.get("data_operazione")),
            "data_valuta": (row.get("data_valuta")),
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
            import math

            def make_json_serializable(obj):
                """Converte ricorsivamente tipi non-JSON-serializable in tipi nativi Python."""
                if isinstance(obj, pd.Timestamp):
                    return obj.isoformat() if not pd.isna(obj) else None
                if isinstance(obj, float) and math.isnan(obj):
                    return None
                return obj

            # Prima dell'upsert, sanitizza ogni record
            batch_data = [
                {k: make_json_serializable(v) for k, v in record.items()}
                for record in batch_data
            ]

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
    
def get_rendimento_annuo():
    """
    Recupera i dati di rendimento annuo dal database Supabase.

    Usa la vista v_portafoglio_rendimento_annuo_twr, che calcola il rendimento
    annuale componendo i rendimenti mensili time-weighted (coerente con il
    grafico Performance). In fallback usa la vecchia vista annuale.

    Ritorna:
        list: Lista di dizionari contenenti i dati di rendimento annuo
    """
    try:
        response = supabase.table("v_portafoglio_rendimento_annuo_twr").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero del rendimento annuo (twr): {e}")
        try:
            response = supabase.table("v_portafoglio_rendimento_annuo").select("*").execute()
            return response.data
        except Exception as e2:
            logging.error(f"Errore durante il recupero del rendimento annuo (fallback): {e2}")
            return []
    
def insert_bond_coupons(coupons):
    """
    Inserisce (upsert idempotente) le cedole obbligazionarie nella tabella
    bond_coupons.

    Parametri:
        coupons (list[dict]): ogni dict con chiavi:
            ticker, isin, descrizione, data_operazione (ISO str),
            data_valuta (ISO str | None), importo_lordo_eur, ritenuta_eur,
            importo_netto_eur, protocollo_cedola (str), protocollo_ritenuta (str|None)

    L'upsert usa protocollo_cedola come chiave di conflitto: ricaricare lo
    stesso file non crea duplicati.

    Ritorna:
        response | None
    """
    if not coupons:
        return None
    try:
        response = supabase.table("bond_coupons").upsert(
            coupons,
            on_conflict="protocollo_cedola",
            ignore_duplicates=False,
        ).execute()
        logging.info(f"Inserite/aggiornate {len(coupons)} cedole obbligazionarie.")
        return response
    except Exception as e:
        logging.error(f"Errore durante l'inserimento delle cedole: {e}")
        return None


def get_bond_coupons():
    """
    Recupera tutte le cedole obbligazionarie incassate dalla tabella bond_coupons.

    Ritorna:
        list: Lista di dizionari con le cedole
    """
    try:
        response = (
            supabase.table("bond_coupons")
            .select("*")
            .order("data_operazione", desc=True)
            .execute()
        )
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero delle cedole: {e}")
        return []


def get_portfolio_overview():
    """
    Recupera il riepilogo complessivo del portafoglio (ETF + Obbligazioni)
    dalla vista v_portfolio_overview.

    Ogni riga: asset_class, investito_eur, valore_attuale_eur, guadagno_eur,
    rendimento_pct. I bond sono valorizzati al costo (nessun prezzo live).

    Ritorna:
        list: Lista di dizionari con il riepilogo per asset class
    """
    try:
        response = supabase.table("v_portfolio_overview").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero dell'overview portafoglio: {e}")
        return []


def get_bond_summary():
    """
    Recupera il riepilogo per singola obbligazione dalla vista v_bond_summary.

    Ogni riga: ticker, isin, descrizione, prima_data_acquisto, nominale_totale,
    capitale_investito_eur, tasso_cedolare_pct, giorni_detenzione,
    cedola_annua_attesa_eur, cedole_maturate_stimate_eur, cedole_incassate_eur.

    Nota: le cedole maturate sono una STIMA per i BTP a tasso fisso
    (nominale * tasso * giorni/365); per i titoli indicizzati i campi cedolari
    sono None. Le cedole incassate reali sono 0 finche' non vengono registrate
    transazioni di tipo cedola.

    Ritorna:
        list: Lista di dizionari con il riepilogo per obbligazione
    """
    try:
        response = supabase.table("v_bond_summary").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero del riepilogo bond: {e}")
        return []


def get_rendimento_mensile():
    """
    Recupera il rendimento mensile (time-weighted) del portafoglio dalla vista
    v_portafoglio_rendimento_mensile.

    Ogni riga contiene: anno, mese, periodo (YYYY-MM), valore_fine_mese_eur,
    flusso_netto_eur, rendimento_mensile_pct, rendimento_cumulato_ytd_pct.

    Ritorna:
        list: Lista di dizionari con il rendimento mensile del portafoglio
    """
    try:
        response = (
            supabase.table("v_portafoglio_rendimento_mensile")
            .select("*")
            .order("periodo")
            .execute()
        )
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero del rendimento mensile: {e}")
        return []


def get_rendimento_cumulato():
    """
    Recupera il rendimento cumulato "since inception" (time-weighted) del
    portafoglio dalla vista v_portafoglio_rendimento_cumulato.

    Ogni riga contiene: periodo (YYYY-MM), anno, mese,
    rendimento_cumulato_totale_pct.

    Ritorna:
        list: Lista di dizionari con il rendimento cumulato totale del portafoglio
    """
    try:
        response = (
            supabase.table("v_portafoglio_rendimento_cumulato")
            .select("*")
            .order("periodo")
            .execute()
        )
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero del rendimento cumulato: {e}")
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
     
def get_etf_history():
    """
    Recupera lo storico dei prezzi degli ETF dal database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti lo storico per ETF
    """
    try:
        all_data = []
        page_size = 1000
        start = 0
        
        while True:
            response = supabase.table("etf_price_history").select("*").range(start, start + page_size - 1).execute()
            all_data.extend(response.data)
            
            if len(response.data) < page_size:
                break
            
            start += page_size
        
        return all_data
    except Exception as e:
        logging.error(f"Errore durante il recupero dello storico ETF: {e}")
        return [] 
    
def get_etf_correlations():
    """
    Recupera lo storico dei prezzi degli ETF dal database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti lo storico per ETF
    """
    try:
        all_data = []
        page_size = 1000
        start = 0
        
        while True:
            response = supabase.table("etf_correlations").select("*").range(start, start + page_size - 1).execute()
            all_data.extend(response.data)
            
            if len(response.data) < page_size:
                break
            
            start += page_size
        
        return all_data
    except Exception as e:
        logging.error(f"Errore durante il recupero dello storico ETF: {e}")
        return [] 
        
def insert_etf_correlation(correlation_data):
    # Usa upsert per inserire o aggiornare se esiste già
    response = supabase.table("etf_correlations")\
        .upsert(correlation_data, on_conflict="etf_symbol_1,etf_symbol_2")\
        .execute()
    
    logging.info(f"Correlazione salvata con successo nel database.")
    return response

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
    
def get_asset_allocation():
    """
    Recupera l'asset allocation del portafoglio dal database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti l'asset allocation
    """
    try:
        response = supabase.table("v_asset_allocation").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero dell'asset allocation: {e}")
        return []   
    
def get_bond_transactions():
    """
    Recupera le transazioni obbligazionarie dal database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti le transazioni obbligazionarie
    """
    try:
        response = supabase.table("transaction").select("*").like("ticker", "M.%").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero delle transazioni obbligazionarie: {e}")
        return []   
     
def get_rendimento_cedole():
    """
    Recupera il rendimento delle cedole dal database Supabase.
    
    Ritorna:
        list: Lista di dizionari contenenti il rendimento delle cedole
    """
    try:
        response = supabase.table("v_rendimento_cedole").select("*").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero del rendimento delle cedole: {e}")

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

from supabase import Client
from datetime import date, datetime

def insert_transaction(
    data_operazione: date,
    ticker: str,
    protocollo: int,
    riferimento_ordine: str,
    tipo_operazione: str = 'Acquisto',
    isin: str = '',
    descrizione: str = '',
    importo_euro: float = 0,
    importo_divisa: float = 0.0,
    divisa: str = '',
    quantita: float = 0.0,
    intermediario: str = ''
):
    """
    Inserisce una transazione nella tabella transaction
    """
    data = {
        "data_operazione" : data_operazione.isoformat(),  # Converti in formato ISO
        "data_valuta": data_operazione.isoformat(),
        "ticker": ticker,
        "protocollo": protocollo,
        "riferimento_ordine": riferimento_ordine
    }
    
    # Aggiungi campi opzionali solo se presenti
    if tipo_operazione:
        data["tipo_operazione"] = tipo_operazione
    if isin:
        data["isin"] = isin
    if descrizione:
        data["descrizione"] = descrizione
    if importo_euro is not None:
        data["importo_euro"] = - importo_euro
    if importo_divisa is not None:
        data["importo_divisa"] = importo_divisa
    if divisa:
        data["divisa"] = divisa
    if quantita is not None:
        data["quantita"] = quantita
    if intermediario:
        data["intermediario"] = intermediario
    
    response = supabase.table("transaction").insert(data).execute()
    return response

# ---------------------------------------------------------------------------
# Gestione Spese - Conti, Categorie, Sotto-Categorie
# ---------------------------------------------------------------------------

def get_conti():
    """
    Recupera tutti i conti dalla tabella "conti" del database Supabase.

    Ritorna:
        list: Lista di dizionari con i conti (id, nome). Lista vuota in errore.
    """
    try:
        response = supabase.table("conti").select("*").order("nome").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero dei conti: {e}")
        return []


def upsert_conto(nome):
    """
    Inserisce un conto nella tabella "conti" in modo idempotente.

    L'upsert usa "nome" come chiave di conflitto con ignore_duplicates=True:
    ricaricare un conto gia' esistente non crea duplicati e non genera errore.

    Parametri:
        nome (str): Nome del conto

    Ritorna:
        response | None: Risultato dell'upsert, None in caso di errore
    """
    try:
        response = supabase.table("conti").upsert(
            {"nome": nome},
            on_conflict="nome",
            ignore_duplicates=True,
        ).execute()
        return response
    except Exception as e:
        logging.error(f"Errore durante l'upsert del conto '{nome}': {e}")
        return None


def get_or_create_conto(nome):
    """
    Restituisce l'id del conto con il nome indicato, creandolo se non esiste.

    Prima tenta un upsert idempotente (ignora i duplicati), poi legge l'id del
    conto corrispondente al nome. Funziona sia che il conto esistesse gia' sia
    che sia stato appena creato.

    Parametri:
        nome (str): Nome del conto

    Ritorna:
        int | None: id del conto, None in caso di errore
    """
    try:
        # Crea il conto se non esiste (idempotente)
        upsert_conto(nome)
        response = (
            supabase.table("conti")
            .select("id")
            .eq("nome", nome)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]["id"]
        return None
    except Exception as e:
        logging.error(f"Errore durante get_or_create del conto '{nome}': {e}")
        return None


def get_categorie():
    """
    Recupera tutte le categorie dalla tabella "categorie" del database Supabase.

    Ritorna:
        list: Lista di dizionari con le categorie (id, nome). Lista vuota in errore.
    """
    try:
        response = supabase.table("categorie").select("*").order("nome").execute()
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero delle categorie: {e}")
        return []


def upsert_categoria(nome):
    """
    Inserisce una categoria nella tabella "categorie" in modo idempotente.

    L'upsert usa "nome" come chiave di conflitto con ignore_duplicates=True:
    ricaricare una categoria gia' esistente non crea duplicati.

    Parametri:
        nome (str): Nome della categoria

    Ritorna:
        response | None: Risultato dell'upsert, None in caso di errore
    """
    try:
        response = supabase.table("categorie").upsert(
            {"nome": nome},
            on_conflict="nome",
            ignore_duplicates=True,
        ).execute()
        return response
    except Exception as e:
        logging.error(f"Errore durante l'upsert della categoria '{nome}': {e}")
        return None


def get_sotto_categorie():
    """
    Recupera tutte le sotto-categorie dalla tabella "sotto_categorie".

    Ritorna:
        list: Lista di dizionari con le sotto-categorie (id, categoria_id, nome).
              Lista vuota in caso di errore.
    """
    try:
        response = (
            supabase.table("sotto_categorie")
            .select("*")
            .order("nome")
            .execute()
        )
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero delle sotto-categorie: {e}")
        return []


def upsert_sotto_categoria(nome, categoria_id):
    """
    Inserisce una sotto-categoria nella tabella "sotto_categorie" in modo
    idempotente.

    L'upsert usa (categoria_id, nome) come chiave di conflitto con
    ignore_duplicates=True: la stessa sotto-categoria nella stessa categoria
    non viene duplicata.

    Parametri:
        nome (str): Nome della sotto-categoria
        categoria_id (int): id della categoria di appartenenza

    Ritorna:
        response | None: Risultato dell'upsert, None in caso di errore
    """
    try:
        response = supabase.table("sotto_categorie").upsert(
            {"nome": nome, "categoria_id": categoria_id},
            on_conflict="categoria_id, nome",
            ignore_duplicates=True,
        ).execute()
        return response
    except Exception as e:
        logging.error(
            f"Errore durante l'upsert della sotto-categoria '{nome}' "
            f"(categoria_id={categoria_id}): {e}"
        )
        return None


def insert_trasferimento(conto_origine_id, conto_dest_id, importo_eur, data_iso, nota=None):
    """
    Registra un Trasferimento tra due Conti inserendo due Movimenti speculari
    in modo atomico tramite compensazione applicativa (Req 7.1, 7.2).

    Crea due righe nella tabella "movimenti" con pari importo (assoluto) e pari
    data valuta:
      - "Trasferimento uscita" sul Conto di origine (importo negativo)
      - "Trasferimento ingresso" sul Conto di destinazione (importo positivo)

    Supabase/PostgREST non espone transazioni multi-statement lato client,
    quindi l'atomicita' e' garantita per compensazione: se l'inserimento del
    secondo Movimento fallisce, il primo (gia' inserito) viene rimosso, in modo
    da non lasciare meta' Trasferimento ne' alterare i saldi dei Conti (Req 7.2).

    Parametri:
        conto_origine_id (int): id del Conto di origine (lato "uscita")
        conto_dest_id (int): id del Conto di destinazione (lato "ingresso")
        importo_eur (float): importo del Trasferimento (verra' usato in valore
            assoluto: negativo in uscita, positivo in ingresso)
        data_iso (str): data valuta in formato ISO (YYYY-MM-DD), uguale per
            entrambi i Movimenti
        nota (str | None): nota opzionale associata al Trasferimento

    Ritorna:
        response | None: risultato dell'inserimento del secondo Movimento in
            caso di successo, None in caso di errore (con compensazione gia'
            eseguita sul primo Movimento).
    """
    importo = abs(importo_eur)
    descr = (nota or "").strip() or "Trasferimento tra conti"
    descr_norm = descr.upper()

    movimento_uscita = {
        "data_movimento": data_iso,
        "conto_id": conto_origine_id,
        "importo_eur": -importo,
        "tipo_movimento": "Trasferimento uscita",
        "valuta": "EUR",
        "nota": nota,
        "descrizione": descr,
        "descrizione_normalizzata": descr_norm,
    }
    movimento_ingresso = {
        "data_movimento": data_iso,
        "conto_id": conto_dest_id,
        "importo_eur": importo,
        "tipo_movimento": "Trasferimento ingresso",
        "valuta": "EUR",
        "nota": nota,
        "descrizione": descr,
        "descrizione_normalizzata": descr_norm,
    }

    # 1) Inserisci il lato "uscita" sul conto di origine
    try:
        res_uscita = supabase.table("movimenti").insert(movimento_uscita).execute()
    except Exception as e:
        logging.error(
            f"Errore durante l'inserimento del lato uscita del trasferimento "
            f"(conto_origine_id={conto_origine_id}): {e}"
        )
        return None

    # 2) Inserisci il lato "ingresso" sul conto di destinazione; in caso di
    #    fallimento, compensa rimuovendo il lato uscita gia' inserito.
    try:
        res_ingresso = supabase.table("movimenti").insert(movimento_ingresso).execute()
        return res_ingresso
    except Exception as e:
        logging.error(
            f"Errore durante l'inserimento del lato ingresso del trasferimento "
            f"(conto_dest_id={conto_dest_id}): {e}. Avvio compensazione del "
            f"lato uscita gia' inserito."
        )
        # Compensazione: elimina il movimento di uscita appena creato
        try:
            inserted = getattr(res_uscita, "data", None) or []
            for riga in inserted:
                movimento_id = riga.get("id")
                if movimento_id is not None:
                    supabase.table("movimenti").delete().eq("id", movimento_id).execute()
            logging.info(
                "Compensazione completata: lato uscita del trasferimento rimosso."
            )
        except Exception as e2:
            logging.error(
                f"Errore durante la compensazione del lato uscita del "
                f"trasferimento: {e2}. Possibile Movimento orfano da verificare."
            )
        return None

# ---------------------------------------------------------------------------
# Gestione Spese - Mapping Esercente -> Categoria
# ---------------------------------------------------------------------------

def get_mapping_esercente():
    """
    Recupera tutte le voci del Mapping_Esercente_Categoria dalla tabella
    "mapping_esercente_categoria" del database Supabase (Req 6.1, 9.1).

    Ogni riga: id, esercente_normalizzato, categoria_id, sotto_categoria_id.
    L'Auto_Categorizzatore usa queste voci per assegnare Categoria (e
    Sotto_Categoria) di default ai Movimenti in base all'Esercente normalizzato.

    Ritorna:
        list: Lista di dizionari con le voci di mapping. Lista vuota in errore.
    """
    try:
        response = (
            supabase.table("mapping_esercente_categoria")
            .select("*")
            .order("esercente_normalizzato")
            .execute()
        )
        return response.data
    except Exception as e:
        logging.error(f"Errore durante il recupero del mapping esercente->categoria: {e}")
        return []


def upsert_mapping_esercente(esercente_norm, categoria_id, sotto_categoria_id):
    """
    Inserisce o aggiorna una voce del Mapping_Esercente_Categoria nella tabella
    "mapping_esercente_categoria" (Req 6.5, 6.6).

    L'upsert usa "esercente_normalizzato" come chiave di conflitto con
    ignore_duplicates=False: a differenza degli altri upsert idempotenti, qui
    in caso di conflitto la riga esistente VIENE aggiornata con la nuova
    Categoria e Sotto_Categoria. Questo copre sia la creazione di una nuova voce
    per un Esercente non ancora mappato (Req 6.5) sia la correzione di una voce
    gia' esistente (Req 6.6).

    Parametri:
        esercente_norm (str): Esercente normalizzato, chiave del mapping
        categoria_id (int): id della Categoria di default (obbligatoria)
        sotto_categoria_id (int | None): id della Sotto_Categoria di default
            (facoltativa, None se non presente)

    Ritorna:
        response | None: Risultato dell'upsert, None in caso di errore
    """
    try:
        response = supabase.table("mapping_esercente_categoria").upsert(
            {
                "esercente_normalizzato": esercente_norm,
                "categoria_id": categoria_id,
                "sotto_categoria_id": sotto_categoria_id,
            },
            on_conflict="esercente_normalizzato",
            ignore_duplicates=False,
        ).execute()
        return response
    except Exception as e:
        logging.error(
            f"Errore durante l'upsert del mapping esercente '{esercente_norm}' "
            f"(categoria_id={categoria_id}, sotto_categoria_id={sotto_categoria_id}): {e}"
        )
        return None

# ---------------------------------------------------------------------------
# Gestione Spese - Movimenti (CRUD + UPSERT idempotente)
# ---------------------------------------------------------------------------

def get_movimenti(conto=None, categoria=None, data_da=None, data_a=None):
    """
    Recupera i Movimenti dalla tabella "movimenti" con filtri opzionali,
    ordinati per data_movimento decrescente, con paginazione a pagine di 1000
    righe come get_etf_history (Req 8.1, 8.3, 8.4, 8.5).

    I filtri "conto" e "categoria" possono essere passati sia come id numerico
    sia come nome: in quest'ultimo caso il nome viene risolto nell'id
    corrispondente tramite le tabelle "conti" / "categorie" prima di applicare
    il filtro su conto_id / categoria_id. Se un nome non viene risolto, il
    relativo filtro produce un elenco vuoto (nessun movimento corrispondente).

    Parametri:
        conto (int | str | None): id o nome del Conto per cui filtrare (Req 8.3)
        categoria (int | str | None): id o nome della Categoria (Req 8.4)
        data_da (str | None): data iniziale inclusa, ISO YYYY-MM-DD (Req 8.5)
        data_a (str | None): data finale inclusa, ISO YYYY-MM-DD (Req 8.5)

    Ritorna:
        list: Lista di dizionari con i movimenti. Lista vuota in caso di errore
              o se nessun movimento soddisfa i filtri.
    """
    try:
        def _risolvi_id(valore, tabella):
            """Restituisce l'id: se valore e' gia' numerico lo usa, altrimenti
            lo cerca per nome nella tabella indicata. None se non risolvibile."""
            if valore is None:
                return None
            if isinstance(valore, int):
                return valore
            if isinstance(valore, str) and valore.isdigit():
                return int(valore)
            # Risoluzione per nome
            res = (
                supabase.table(tabella)
                .select("id")
                .eq("nome", valore)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]["id"]
            return None

        conto_id = None
        if conto is not None:
            conto_id = _risolvi_id(conto, "conti")
            if conto_id is None:
                # Nome conto non trovato: nessun movimento corrispondente
                return []

        categoria_id = None
        if categoria is not None:
            categoria_id = _risolvi_id(categoria, "categorie")
            if categoria_id is None:
                # Nome categoria non trovato: nessun movimento corrispondente
                return []

        all_data = []
        page_size = 1000
        start = 0

        while True:
            query = supabase.table("movimenti").select("*")

            if conto_id is not None:
                query = query.eq("conto_id", conto_id)
            if categoria_id is not None:
                query = query.eq("categoria_id", categoria_id)
            if data_da is not None:
                query = query.gte("data_movimento", data_da)
            if data_a is not None:
                query = query.lte("data_movimento", data_a)

            response = (
                query.order("data_movimento", desc=True)
                .range(start, start + page_size - 1)
                .execute()
            )
            all_data.extend(response.data)

            if len(response.data) < page_size:
                break

            start += page_size

        return all_data
    except Exception as e:
        logging.error(f"Errore durante il recupero dei movimenti: {e}")
        return []


def upsert_movimenti(movimenti):
    """
    Inserisce (UPSERT idempotente) una lista di Movimenti nella tabella
    "movimenti" (Req 3.7, 3.8, 5.1, 5.2, 5.4).

    L'upsert usa la Chiave_Naturale_Movimento come chiave di conflitto
    (data_movimento, conto_id, importo_eur, descrizione_normalizzata) con
    ignore_duplicates=True: ricaricare gli stessi movimenti non crea duplicati
    e non altera i record gia' presenti. Prima dell'upsert ogni record viene
    sanitizzato con make_json_serializable, che converte i Timestamp pandas in
    stringhe ISO e i valori NaN in None, in modo da ottenere payload
    JSON-serializzabili (coerente con insert_directa_transaction).

    Parametri:
        movimenti (list[dict]): Lista di record movimento da salvare.

    Ritorna:
        response | None: Risultato dell'upsert, None in caso di errore o se la
                         lista e' vuota.
    """
    if not movimenti:
        return None
    try:
        import math

        def make_json_serializable(obj):
            """Converte ricorsivamente tipi non-JSON-serializable in tipi nativi Python."""
            if isinstance(obj, pd.Timestamp):
                return obj.isoformat() if not pd.isna(obj) else None
            if isinstance(obj, float) and math.isnan(obj):
                return None
            return obj

        # Sanitizza ogni record prima dell'upsert
        batch_data = [
            {k: make_json_serializable(v) for k, v in record.items()}
            for record in movimenti
        ]

        response = supabase.table("movimenti").upsert(
            batch_data,
            on_conflict="data_movimento, conto_id, importo_eur, descrizione_normalizzata",
            ignore_duplicates=True,
        ).execute()
        logging.info(f"Upsert di {len(batch_data)} movimenti completato.")
        return response
    except Exception as e:
        logging.error(f"Errore durante l'upsert dei movimenti: {e}")
        return None


def update_movimento(movimento_id, campi):
    """
    Aggiorna i campi indicati di un Movimento esistente, identificato dall'id
    (Req 8.8).

    Parametri:
        movimento_id (int): id del Movimento da aggiornare
        campi (dict): Dizionario dei campi da aggiornare con i nuovi valori

    Ritorna:
        response | None: Risultato dell'update, None in caso di errore.
    """
    try:
        response = (
            supabase.table("movimenti")
            .update(campi)
            .eq("id", movimento_id)
            .execute()
        )
        return response
    except Exception as e:
        logging.error(
            f"Errore durante l'aggiornamento del movimento id={movimento_id}: {e}"
        )
        return None


def delete_movimento(movimento_id):
    """
    Elimina un Movimento esistente, identificato dall'id (Req 8.10).

    Parametri:
        movimento_id (int): id del Movimento da eliminare

    Ritorna:
        response | None: Risultato della delete, None in caso di errore.
    """
    try:
        response = (
            supabase.table("movimenti")
            .delete()
            .eq("id", movimento_id)
            .execute()
        )
        return response
    except Exception as e:
        logging.error(
            f"Errore durante l'eliminazione del movimento id={movimento_id}: {e}"
        )
        return None

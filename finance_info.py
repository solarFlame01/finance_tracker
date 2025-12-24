import yfinance as yf
from datetime import datetime
import pandas as pd
import streamlit as st
import numpy as np

def aggiorna_prezzi_eft():
    """
    Aggiorna i prezzi correnti di tutti gli ETF
    """
    from database import get_etf_list, insert_update_etf_price
    from finance_info import get_etf_price
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info("Inizio aggiornamento prezzi ETF")
    
    etf_list = get_etf_list()
    logger.info(f"Trovati {len(etf_list)} ETF da aggiornare")
    
    success_count = 0
    for etf in etf_list:
        etf_ticker = etf.get('etf_ticker') if isinstance(etf, dict) else etf
        logger.debug(f"Elaborazione ETF: {etf_ticker}")
        
        price = get_etf_price(etf_ticker)
        if price is not None:
            response = insert_update_etf_price(etf_ticker, price)
            if response is not None:
                logger.info(f"Prezzo aggiornato: {etf_ticker} = {price}")
                success_count += 1
            else:
                st.error(f"❌ Impossibile aggiornare il prezzo per {etf_ticker}")
                logger.error(f"Errore DB per {etf_ticker}")
        else:
            st.error(f"❌ Impossibile recuperare il prezzo per {etf_ticker}")
            logger.warning(f"Prezzo non disponibile per {etf_ticker}")
    
    st.success(f"✅ Prezzi aggiornati")
    st.rerun()
    logger.info(f"Aggiornamento completato: {success_count}/{len(etf_list)} successi")
    
def get_all_etf_history(ticker: str, interval: str = "1d") -> pd.DataFrame:
    """
    Recupera lo storico COMPLETO prezzi (e dividendi) da Yahoo Finance
    provando prima .MI, poi .DE, poi senza suffix.
    
    Args:
        ticker: Base ticker (es: 'CSPX', 'EIMI')
        interval: es. '1d', '1wk', '1mo'
    
    Returns:
        DataFrame con colonne: ['ticker','date','close','dividends']
    """
    # Lista di suffix da provare (in ordine di priorità)
    suffixes = ['.MI', '.DE', '.L', '.AS']  # Aggiunto .L (London), .AS (Amsterdam)
    
    for suffix in suffixes + [None]:  # + None per ticker "puro"
        try:
            full_ticker = f"{ticker}{suffix}" if suffix else ticker
            print(f"🔍 Provo ticker: {full_ticker}")
            
            etf = yf.Ticker(full_ticker)
            history = etf.history(
                period="max",
                interval=interval,
                auto_adjust=False
            )

            if history is None or history.empty:
                print(f"📭 Nessun dato per {full_ticker}, passo al successivo...")
                continue  # Prova prossimo suffix invece di return

            history = history.reset_index()
            
            df = pd.DataFrame({
                "ticker": ticker,  # Salva solo base ticker, non suffix
                "date": history["Date"].dt.date,  # Normalizza a date
                "close": history["Close"],
                "dividends": history["Dividends"].fillna(0.0)  # Colonna corretta
            }).dropna(subset=["close"])  # Rimuovi righe senza prezzo
            
            print(f"✅ Dati trovati per {full_ticker}: {len(df)} righe")
            
            # Salva in DB (opzionale)
            try:
                from database import insert_etf_history
                insert_etf_history(df)
            except Exception as db_e:
                print(f"⚠️ Errore DB per {ticker}: {str(db_e)}")
            
            return df
            
        except Exception as e:
            print(f"❌ Errore {full_ticker}: {str(e)}")
            continue  # Prova prossimo suffix
    
    # Se nessuno funziona
    print(f"💥 Nessun ticker valido trovato per '{ticker}'")
    return pd.DataFrame(columns=["ticker", "date", "close", "dividends"])

def calculate_CAGR():
    """
    Calcola il CAGR del portafoglio con calcolo corretto degli anni.
    """
    print("🚀 Inizio calcolo CAGR...")
    
    import pandas as pd
    from datetime import datetime
    
    df_transaction = pd.DataFrame(st.session_state.etf_transactions)
    
    # Controlli di validità
    if df_transaction.empty or 'Costo' not in df_transaction.columns:
        return None
    
    costo_totale = df_transaction['Costo'].sum()
    market_value_totale = df_transaction['Market Value'].sum()
    
    if costo_totale == 0 or market_value_totale == 0:
        return None
    
    # ✅ CORRETTO: Calcola i giorni effettivi tra prima e ultima transazione
    df_transaction['Data acquisto'] = pd.to_datetime(df_transaction['Data acquisto'], errors='coerce')
    
    data_inizio = df_transaction['Data acquisto'].min()
    data_fine = df_transaction['Data acquisto'].max()
    
    giorni_passati = (data_fine - data_inizio).days
    
    # Se tutte le transazioni sono nello stesso giorno, usa almeno 1 anno
    if giorni_passati == 0:
        totale_anni = 1
    else:
        totale_anni = giorni_passati / 365.25  # ✅ Usa 365.25 per anni bisestili
    
    # CAGR formula corretta
    value_ratio = market_value_totale / costo_totale
    cagr = (value_ratio ** (1 / totale_anni)) - 1
    
    print(f"📊 Dettagli calcolo:")
    print(f"   Data inizio: {data_inizio.date()}")
    print(f"   Data fine: {data_fine.date()}")
    print(f"   Giorni passati: {giorni_passati}")
    print(f"   Anni: {totale_anni:.2f}")
    print(f"   Costo totale: {costo_totale:.2f}€")
    print(f"   Market value: {market_value_totale:.2f}€")
    print(f"   Value ratio: {value_ratio:.4f}")
    print(f"   CAGR: {cagr:.4f} ({cagr*100:.2f}%)")
    
    return cagr * 100


def calculate_twr_monthly() -> float:
    """
    Calcola il TWR mensile dato una serie di cash flow e valori di portafoglio.
    
    Args:
        cash_flows (pd.Series): Serie di cash flow mensili (positivi per depositi, negativi per prelievi)
        values (pd.Series): Serie dei valori di portafoglio alla fine di ogni mese
    
    Returns:
        float: TWR mensile in percentuale
    """
    from database import get_etf_transaction_updated, get_etf_history
    
    transactions = get_etf_transaction_updated()
    etf_history = get_etf_history() 
    min_data_acquisto = transactions['data_operazione'].min()
    return 1 * 100  # Ritorna in percentuale  
def get_etf_price(ticker):
    """
    Recupera il prezzo corrente di un ETF da Yahoo Finance.
    Prova prima con il suffisso .MI (mercato italiano), se non disponibile prova con .DE (mercato tedesco).
    
    Args:
        ticker (str): Il ticker dell'ETF (es: 'CSPXJ', 'EIMI', etc.)
    
    Returns:
        float: Il prezzo corrente dell'ETF
        None: Se l'ETF non esiste su nessun mercato o si verifica un errore
    """
    suffixes = ['.MI', '.DE']  # Prova prima .MI, poi .DE
    
    for suffix in suffixes:
        try:
            full_ticker = ticker + suffix
            etf = yf.Ticker(full_ticker)
            
            # Tenta di ottenere il prezzo corrente
            info = etf.info
            
            # Prova diverse chiavi per il prezzo corrente
            price = info.get('currentPrice') or info.get('regularMarketPrice')
            
            if price is None or price == 0:
                # Se non trova currentPrice, prova con i dati storici più recenti
                hist = etf.history(period='1d')
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
            
            # Se il prezzo è trovato, ritorna
            if price is not None and price != 0:
                return price
        
        except Exception as e:
            print(f"⚠️  {ticker}{suffix} non disponibile: {str(e)}")
            continue  # Passa al suffisso successivo
    
    print(f"❌ Errore: {ticker} non trovato su nessun mercato (.MI e .DE)")
    return None


def get_etf_info(ticker):
    """
    Recupera informazioni complete su un ETF.
    
    Args:
        ticker (str): Il ticker dell'ETF
    
    Returns:
        dict: Dizionario con informazioni sull'ETF (nome, prezzo, valuta, etc.)
    """
    try:
        etf = yf.Ticker(ticker)
        info = etf.info
        
        return {
            'ticker': ticker,
            'name': info.get('longName', 'N/A'),
            'price': info.get('currentPrice') or info.get('regularMarketPrice'),
            'currency': info.get('currency', 'N/A'),
            'exchange': info.get('exchange', 'N/A'),
            'sector': info.get('sector', 'N/A'),
            'last_update': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        }
    
    except Exception as e:
        print(f"❌ Errore nel recupero delle informazioni per {ticker}: {str(e)}")
        return None

def get_etf_volatility(ticker: str, period: str = "10y") -> float:
    """
    Calcola la volatilità annualizzata di un ETF basata sugli ultimi 5 anni di dati.

    Args:
        ticker (str): Il ticker dell'ETF (es: 'VWCE.MI').

    Returns:
        float: La volatilità annualizzata, o None se non è possibile calcolarla.
    """
    try:
        # Scarica dati reali
        data = yf.download(ticker, period=period, progress=False)
        if data is None:
            print(f"Nessun dato trovato per {ticker}")
            return 0

        if data.empty:
            print(f"Nessun dato storico trovato per {ticker}")
            return 0

        # Calcola i ritorni giornalieri
        returns = data['Close'].pct_change().dropna()
        if returns.empty:
            print(f"Non è possibile calcolare i ritorni per {ticker}")
            return 0

        # Calcola la volatilità annualizzata (252 giorni di trading in un anno)
        volatility = returns.std() * np.sqrt(252)
        print(f"Volatilità reale {ticker}: {volatility[0]:.3f}")
        return volatility[0] * 100
    except Exception as e:
        print(f"Errore durante il calcolo della volatilità per {ticker}: {e}")
        return 0

def calculate_etf_correlation(ticker1: str, ticker2: str, start_date: str) -> float:
    """
    Calcola la correlazione tra due ETF a partire da una data specifica.

    Args:
        ticker1 (str): Il ticker del primo ETF (es: 'VWCE.MI').
        ticker2 (str): Il ticker del secondo ETF (es: 'SWDA.MI').
        start_date (str): La data di inizio per l'analisi (formato 'YYYY-MM-DD').

    Returns:
        float: Il coefficiente di correlazione, o None se non è possibile calcolarlo.
    """
    try:
        # Scarica i dati storici per entrambi gli ETF
        data1 = yf.download(ticker1, start=start_date, progress=False)
        data2 = yf.download(ticker2, start=start_date, progress=False)

        if data1.empty or data2.empty:
            print(f"Dati non sufficienti per calcolare la correlazione tra {ticker1} e {ticker2}")
            return None

        # Calcola i ritorni giornalieri
        returns1 = data1['Close'].pct_change().dropna()
        returns2 = data2['Close'].pct_change().dropna()

        # Allinea i dati per avere le stesse date
        returns = pd.concat([returns1, returns2], axis=1, join='inner')
        returns.columns = [ticker1, ticker2]

        if len(returns) < 2:
            print("Non ci sono abbastanza dati sovrapposti per calcolare la correlazione.")
            return None
        
        # Calcola la correlazione
        correlation = returns[ticker1].corr(returns[ticker2])
        
        print(f"Correlazione tra {ticker1} e {ticker2} dal {start_date}: {correlation:.4f}")
        return correlation

    except Exception as e:
        print(f"Errore durante il calcolo della correlazione: {e}")
        return None
print(calculate_etf_correlation('VWCE.MI', 'DFNS.MI', '2020-01-01'))
'''# Ottenere il prezzo corrente
prezzo = get_etf_price('CSPXJ.MI')
print(f"Prezzo CSPXJ: €{prezzo}")

# Ottenere informazioni complete
info = get_all_etf_history('EIMI.MI')
print(info)'''
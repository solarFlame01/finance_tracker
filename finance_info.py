import yfinance as yf
from datetime import datetime

def get_etf_price(ticker):
    """
    Recupera il prezzo corrente di un ETF da Yahoo Finance.
    
    Args:
        ticker (str): Il ticker dell'ETF (es: 'CSPXJ', 'EIMI', etc.)
    
    Returns:
        float: Il prezzo corrente dell'ETF
        None: Se l'ETF non esiste o si verifica un errore
    """
    try:
        etf = yf.Ticker(ticker + '.MI')  # Aggiunge il suffisso .MI per il mercato italiano
        # Tenta di ottenere il prezzo corrente
        info = etf.info
        
        # Prova diverse chiavi per il prezzo corrente
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        
        if price is None or price == 0:
            # Se non trova currentPrice, prova con i dati storici più recenti
            hist = etf.history(period='1d')
            if not hist.empty:
                price = hist['Close'].iloc[-1]
        
        return price
    
    except Exception as e:
        print(f"❌ Errore nel recupero del prezzo per {ticker}: {str(e)}")
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


def get_etf_history(ticker, period='1mo'):
    """
    Recupera lo storico dei prezzi di un ETF.
    
    Args:
        ticker (str): Il ticker dell'ETF
        period (str): Periodo (es: '1d', '1mo', '3mo', '1y')
    
    Returns:
        DataFrame: Dataframe con storico prezzi
    """
    try:
        etf = yf.Ticker(ticker)
        history = etf.history(period=period)
        return history
    
    except Exception as e:
        print(f"❌ Errore nel recupero dello storico per {ticker}: {str(e)}")
        return None

'''# Ottenere il prezzo corrente
prezzo = get_etf_price('CSPXJ.MI')
print(f"Prezzo CSPXJ: €{prezzo}")

# Ottenere informazioni complete
info = get_etf_info('EIMI.MI')
print(info)'''
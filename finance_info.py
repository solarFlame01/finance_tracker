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

def get_correlation_between_two_etfs(etf1_ticker: str, etf2_ticker: str):
    """
    Calcola la correlazione tra due specifici ETF.

    Recupera i dati storici per i due ETF specificati, trova la data di inizio comune
    e calcola il coefficiente di correlazione di Pearson tra i loro rendimenti giornalieri.

    Args:
        etf1_ticker (str): Il ticker del primo ETF.
        etf2_ticker (str): Il ticker del secondo ETF.

    Returns:
        float: Il coefficiente di correlazione, compreso tra -1 e 1.
        str: Un messaggio di errore se uno o entrambi gli ETF non sono trovati
             o se non ci sono dati sufficienti.
    """
    from database import get_etf_history
    import pandas as pd

    # 1. Recupera tutto lo storico
    all_history_df = pd.DataFrame(get_etf_history())
    
    if all_history_df.empty:
        return "Errore: Nessun dato storico trovato nel database."

    # 2. Controlla se entrambi gli ETF sono presenti
    available_tickers = all_history_df['ticker'].unique()
    if etf1_ticker not in available_tickers:
        return f"Errore: ETF '{etf1_ticker}' non trovato nel database."
    if etf2_ticker not in available_tickers:
        return f"Errore: ETF '{etf2_ticker}' non trovato nel database."
        
    # 3. Filtra i dati solo per i due ETF di interesse
    filtered_df = all_history_df[all_history_df['ticker'].isin([etf1_ticker, etf2_ticker])]
    filtered_df['date'] = pd.to_datetime(filtered_df['date'])

    # 4. Pivot dei dati per avere i prezzi su colonne separate
    prices_pivot = filtered_df.pivot(index='date', columns='ticker', values='close')

    # 5. Trova la data di inizio comune (la data più recente tra le prime date disponibili)
    first_date_etf1 = prices_pivot[etf1_ticker].first_valid_index()
    first_date_etf2 = prices_pivot[etf2_ticker].first_valid_index()
    
    if pd.isna(first_date_etf1) or pd.isna(first_date_etf2):
        return "Errore: Dati storici insufficienti per uno degli ETF."

    common_start_date = max(first_date_etf1, first_date_etf2)
    print(f"Data inizio comune: {common_start_date.date()}")
    # 6. Filtra il DataFrame pivotato dalla data di inizio comune
    common_prices = prices_pivot.loc[common_start_date:]
    
    # 7. Rimuovi eventuali giorni in cui uno dei due ETF non ha un prezzo
    common_prices = common_prices.dropna()
    
    if len(common_prices) < 2:
        return "Errore: Non ci sono abbastanza dati sovrapposti per calcolare la correlazione."

    # 8. Calcola i rendimenti giornalieri
    returns = common_prices.pct_change().dropna()

    # 9. Calcola la correlazione
    correlation = returns[etf1_ticker].corr(returns[etf2_ticker])
        # 10. Salva nel database se richiesto
    
    # Ordina i ticker per rispettare il constraint CHECK (etf_symbol_1 < etf_symbol_2)
    symbol_1, symbol_2 = sorted([etf1_ticker, etf2_ticker])
    
    # Calcola la data di fine (ultima data disponibile nei dati comuni)
    period_end = common_prices.index.max().date()
    
    # Prepara i dati per l'inserimento
    correlation_data = {
        "etf_symbol_1": symbol_1,
        "etf_symbol_2": symbol_2,
        "correlation_coefficient": float(round(correlation, 8)),
        "sample_size": len(returns),
        "calculation_date": datetime.now().isoformat(),
        "period_start": common_start_date.date().isoformat(),
        "period_end": period_end.isoformat()
    }
    
    from database import insert_etf_correlation
    insert_etf_correlation(correlation_data)
        

    return correlation

def calculate_all_etf_correlations():
    """
    Calcola e salva tutte le correlazioni pairwise tra gli ETF disponibili nel database.
    
    Utilizza itertools.combinations per generare tutte le coppie uniche di ETF
    senza duplicati o coppie ordinate inversamente (es. (A,B) ma non (B,A)).
    
    Returns:
        dict: Dizionario con statistiche sull'esecuzione:
            - total_pairs: numero totale di coppie da calcolare
            - successful: numero di correlazioni calcolate con successo
            - failed: numero di calcoli falliti
            - errors: lista di errori incontrati
    """
    from itertools import combinations
    from database import get_etf_history
    import pandas as pd
    import logging
    
    # Recupera tutti i ticker disponibili
    all_history_df = pd.DataFrame(get_etf_history())
    
    if all_history_df.empty:
        logging.error("Nessun dato storico trovato nel database.")
        return {
            "total_pairs": 0,
            "successful": 0,
            "failed": 0,
            "errors": ["Nessun dato storico trovato"]
        }
    
    available_tickers = sorted(all_history_df['ticker'].unique())
    
    # Genera tutte le coppie uniche di ETF
    etf_pairs = list(combinations(available_tickers, 2))
    
    logging.info(f"Inizio calcolo correlazioni per {len(etf_pairs)} coppie di ETF")
    print(f"Totale coppie da calcolare: {len(etf_pairs)}")
    
    # Statistiche di esecuzione
    stats = {
        "total_pairs": len(etf_pairs),
        "successful": 0,
        "failed": 0,
        "errors": []
    }
    
    # Calcola la correlazione per ogni coppia
    for i, (etf1, etf2) in enumerate(etf_pairs, 1):
        try:
            print(f"[{i}/{len(etf_pairs)}] Calcolo correlazione: {etf1} <-> {etf2}")
            
            result = get_correlation_between_two_etfs(etf1, etf2)
            
            # Verifica se il risultato è un numero valido
            if isinstance(result, float):
                stats["successful"] += 1
                logging.info(f"Correlazione {etf1}-{etf2}: {result:.4f}")
            else:
                # Il risultato è un messaggio di errore
                stats["failed"] += 1
                stats["errors"].append(f"{etf1}-{etf2}: {result}")
                logging.warning(f"Errore per coppia {etf1}-{etf2}: {result}")
                
        except Exception as e:
            stats["failed"] += 1
            error_msg = f"{etf1}-{etf2}: {str(e)}"
            stats["errors"].append(error_msg)
            logging.error(f"Eccezione durante il calcolo per {etf1}-{etf2}: {e}")
    
    # Riepilogo finale
    print("\n" + "="*50)
    print("RIEPILOGO CALCOLO CORRELAZIONI")
    print("="*50)
    print(f"Totale coppie: {stats['total_pairs']}")
    print(f"Successi: {stats['successful']}")
    print(f"Fallimenti: {stats['failed']}")
    print(f"Tasso di successo: {stats['successful']/stats['total_pairs']*100:.1f}%")
    
    if stats['errors']:
        print(f"\nErrori riscontrati ({len(stats['errors'])}):")
        for error in stats['errors'][:10]:  # Mostra solo i primi 10 errori
            print(f"  - {error}")
        if len(stats['errors']) > 10:
            print(f"  ... e altri {len(stats['errors'])-10} errori")
    
    logging.info(f"Calcolo completato: {stats['successful']}/{stats['total_pairs']} correlazioni salvate")
    
    return stats

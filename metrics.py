import pandas as pd

def calculate_metrics(transactions):
    """
    Calcola metriche base per una lista di transazioni ETF.
    Ritorna un DataFrame con colonne aggiuntive: Costo, Market Value, Crescita %.
    """
    if not transactions:
        return pd.DataFrame()
    
    df = pd.DataFrame(transactions)
    
    # Assicura la presenza delle colonne necessarie
    required_cols = ['Quantità', 'Prezzo di acquisto', 'Prezzo corrente']
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0

    # Calcoli principali
    df['Costo'] = df['Quantità'] * df['Prezzo di acquisto']
    df['Market Value'] = df['Quantità'] * df['Prezzo corrente']
    df['Crescita %'] = ((df['Market Value'] - df['Costo']) / df['Costo'] * 100).round(2)

    # Formattazione data
    if 'Data acquisto' in df.columns:
        df['Data acquisto'] = pd.to_datetime(df['Data acquisto'], errors='coerce').dt.strftime('%d/%m/%Y')

    # Arrotondamento colonne numeriche
    numeric_cols = ['Prezzo di acquisto', 'Prezzo corrente', 'Costo', 'Market Value']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].round(2)

    return df

# =========================
# Placeholder per metriche avanzate
# =========================

def sharpe_ratio(returns, risk_free_rate=0.0):
    """
    Calcola lo Sharpe Ratio di una serie di rendimenti.
    """
    excess_returns = returns - risk_free_rate
    if excess_returns.std() == 0:
        return 0
    return excess_returns.mean() / excess_returns.std()

def sortino_ratio(returns, risk_free_rate=0.0):
    """
    Calcola il Sortino Ratio di una serie di rendimenti.
    """
    negative_returns = returns[returns < risk_free_rate]
    downside_std = negative_returns.std() if len(negative_returns) > 0 else 0.0
    if downside_std == 0:
        return 0
    excess_returns = returns - risk_free_rate
    return excess_returns.mean() / downside_std

def max_drawdown(values):
    """
    Calcola il massimo drawdown di una serie di valori.
    """
    cumulative = values.cummax()
    drawdown = (values - cumulative) / cumulative
    return drawdown.min()

# Altre metriche avanzate (beta, alpha, R2, VaR, volatilità, ecc.) possono essere aggiunte qui.
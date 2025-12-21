import streamlit as st
from metrics import calculate_metrics
import plotly.graph_objects as go
import pandas as pd

# Sezione Dashboard
def render_dashboard():
    st.header("📊 Dashboard")
    
    if st.session_state.etf_transactions:
        '''df = calculate_metrics(st.session_state.etf_data)
        
        # Statistiche riepilogative
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            costo_totale = df['Costo'].sum() if 'Costo' in df.columns else 0
            st.metric("Totale Investito", f"€{costo_totale:,.2f}")
        with col2:
            market_value_totale = df['Market Value'].sum() if 'Market Value' in df.columns else 0
            st.metric("Valore di Mercato", f"€{market_value_totale:,.2f}")
        with col3:
            crescita_totale = market_value_totale - costo_totale
            st.metric("Guadagno/Perdita", f"€{crescita_totale:,.2f}")
        with col4:
            rendimento_perc = (crescita_totale / costo_totale * 100) if costo_totale > 0 else 0
            st.metric("Rendimento %", f"{rendimento_perc:.2f}%")
        '''
        # Tabella principale
        st.subheader("Lista ETF")
        
        # Tabella con dati recuperati dal database
        
        df_transaction = pd.DataFrame(st.session_state.etf_transactions)
        # Esclude colonne non desiderate
        df_transaction = df_transaction.drop(columns=[col for col in ["id", "created_at", "updated_at"] if col in df_transaction.columns], errors='ignore')
        st.dataframe(df_transaction, use_container_width=True)
        
        df_bottom_3_etf = pd.DataFrame(st.session_state.bottom_3_etf)
        st.dataframe(df_bottom_3_etf, use_container_width=True)

        df_top_3_etf = pd.DataFrame(st.session_state.top_3_etf)
        # Esclude colonne non desiderate
        st.dataframe(df_top_3_etf, use_container_width=True)
        
        df_portfolio_kpi_etf = pd.DataFrame(st.session_state.kpi_etf)
        # Esclude colonne non desiderate
        st.dataframe(df_portfolio_kpi_etf, use_container_width=True)
        
        # Diagrammi a torta
        st.subheader("Analisi Portfolio")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.session_state.distribuzione_etf:
                df_dist_etf = pd.DataFrame(st.session_state.distribuzione_etf)
                if not df_dist_etf.empty:
                    fig1 = go.Figure(data=[go.Pie(
                        labels=df_dist_etf['ticker'],           
                        values=df_dist_etf['distribuzione_pct'], 
                    )])
                    fig1.update_layout(title="Distribuzione per ETF", height=400)
                    st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # Pie chart: Distribuzione per Settore
            if st.session_state.distribuzione_settore:
                df_dist_settore = pd.DataFrame(st.session_state.distribuzione_settore)
                if not df_dist_settore.empty:
                    fig2 = go.Figure(data=[go.Pie(
                        labels=df_dist_settore['settore'],
                        values=df_dist_settore['distribuzione_pct'],
                    )])
                    fig2.update_layout(title="Distribuzione per Settore", height=400)
                    st.plotly_chart(fig2, use_container_width=True)
        
        col3, col4 = st.columns(2)
        
        with col3:
            # Pie chart: Distribuzione per Valuta di Mercato
            if st.session_state.distribuzione_valuta_mercato:
                df_dist_valuta = pd.DataFrame(st.session_state.distribuzione_valuta_mercato)
                if not df_dist_valuta.empty:
                    fig3 = go.Figure(data=[go.Pie(
                        labels=df_dist_valuta['valuta_mercato'],
                        values=df_dist_valuta['distribuzione_pct'],
                    )])
                    fig3.update_layout(title="Distribuzione per Valuta di Mercato", height=400)
                    st.plotly_chart(fig3, use_container_width=True)
        
        with col4:
            # Pie chart: Distribuzione per Area Geografica
            if st.session_state.distribuzione_area_geografica:
                df_dist_area = pd.DataFrame(st.session_state.distribuzione_area_geografica)
                if not df_dist_area.empty:
                    fig4 = go.Figure(data=[go.Pie(
                        labels=df_dist_area['area_geografica'],
                        values=df_dist_area['distribuzione_pct'],
                    )])
                    fig4.update_layout(title="Distribuzione per Area Geografica", height=400)
                    st.plotly_chart(fig4, use_container_width=True)
        
    else:
        # Tabella con dati finti
        data_finti = {
            "Ticker": ["AUWI", "SUAS", "XDW0", "SMEA", "EIMI", "RBOT", "PHPT", "NUCL", "SUAS", "XDW0", "SJPA"],
            "Quantità": [51, 15, 3, 1, 2, 9, 1, 1, 16, 3, 1],
            "Prezzo di acquisto (€)": [45.74, 14.55, 44.33, 87.36, 35.34, 13.14, 107.92, 42.82, 14.78, 45.18, 56.19],
            "Prezzo corrente (€)": [45.52, 15.22, 45.52, 92.91, 37.50, 13.67, 150.74, 45.60, 15.22, 45.52, 58.59],
            "Costo (€)": [2332.74, 218.25, 132.99, 87.36, 70.68, 118.26, 107.92, 42.82, 236.48, 135.54, 56.19],
            "Market Value (€)": [2321.52, 228.24, 136.56, 92.91, 75.00, 123.03, 150.74, 45.60, 243.46, 136.56, 58.59],
            "Crescita %": [-0.48, 4.58, 2.68, 6.35, 6.11, 4.03, 39.68, 6.49, 2.95, 0.75, 4.27],
            "Valuta": ["EUR", "EUR", "EUR", "EUR", "EUR", "EUR", "EUR", "EUR", "EUR", "EUR", "EUR"],
            "Data acquisto": ["2025-09-23", "2025-09-08", "2025-09-08", "2025-09-08", "2025-09-08", "2025-09-08", "2025-09-08", "2025-09-08", "2025-08-25", "2025-08-25", "2025-08-25"],
            "Emittente": ["iShares", "iShares", "XTRACKERS", "iShares", "iShares", "iShares", "Wisdom Tree", "Vaneck", "iShares", "XTRACKERS", "iShares"],
            "ISIN": ["IE00BG6THM91", "IE00BYJRR92", "IE00BM67THM91", "IE00B4K48X80", "IE00BKM4GZ66", "IE00BYZK4552", "JE00B1VS2W53", "IE00M7V94E1", "IE00BYJRR92", "IE00BM67THM91", "IE00B4L5YX21"]
        }
        
        df_finti = pd.DataFrame(data_finti)
        st.dataframe(df_finti, use_container_width=True)
        st.info("Nessuna transazione ETF presente. Aggiungine una nella sezione 'Gestione ETF'.")
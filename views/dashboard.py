import streamlit as st
from metrics import calculate_metrics
import plotly.graph_objects as go

# Sezione Dashboard
def render_dashboard():
    st.header("📊 Dashboard")
    
    if st.session_state.etf_data:
        df = calculate_metrics(st.session_state.etf_data)
        
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
        
        # Tabella principale
        st.subheader("Lista ETF")
        
        # Colonne disponibili
        colonne_disponibili = {
            "Ticker": "Ticker",
            "Quantità": "Quantità",
            "Prezzo di acquisto": "Prezzo di acquisto",
            "Prezzo corrente": "Prezzo corrente",
            "Costo": "Costo",
            "Market Value": "Market Value",
            "Crescita %": "Crescita %",
            "Valuta": "Valuta",
            "Data acquisto": "Data acquisto",
            "Emittente": "Emittente",
            "ISIN": "ISIN"
        }
        
        # Filtra solo le colonne che esistono nel dataframe
        colonne_esistenti = [col for col in colonne_disponibili.keys() 
                           if colonne_disponibili[col] in df.columns]
        
        if colonne_esistenti:
            colonne_selezionate = st.multiselect(
                "Seleziona colonne da visualizzare:",
                options=colonne_esistenti,
                default=colonne_esistenti[:min(8, len(colonne_esistenti))]
            )
            
            # Mostra tabella
            if colonne_selezionate:
                df_display = df[[colonne_disponibili[col] for col in colonne_selezionate]]
                st.dataframe(df_display, width='stretch', height=400)
            
            # Grafico a barre per performance
            st.subheader("Performance per ETF")
            fig = go.Figure(data=[
                go.Bar(name='Costo', x=df['Ticker'], y=df['Costo']),
                go.Bar(name='Valore Mercato', x=df['Ticker'], y=df['Market Value'])
            ])
            fig.update_layout(barmode='group', height=400)
            st.plotly_chart(fig, width='stretch')
        else:
            st.warning("Nessuna colonna disponibile da visualizzare.")
        
    else:
        st.info("Nessuna transazione ETF presente. Aggiungine una nella sezione 'Gestione ETF'.")
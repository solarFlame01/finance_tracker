import streamlit as st
from metrics import calculate_metrics
import plotly.graph_objects as go
import pandas as pd

# Stili CSS per migliorare l'aspetto
def apply_dashboard_styling():
    st.markdown("""
    <style>
        /* Contenitori principali */
        .metric-container {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
            color: white;
            text-align: center;
        }
        
        /* Titoli sezioni */
        .section-title {
            font-size: 1.3em;
            font-weight: 600;
            margin-top: 25px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }
        
        /* Sottotitoli */
        .subsection-title {
            font-size: 1.1em;
            font-weight: 500;
            margin-top: 15px;
            margin-bottom: 10px;
            color: #667eea;
        }
        
        /* Divider */
        .divider {
            margin: 20px 0;
            border-top: 2px solid #e0e0e0;
        }
    </style>
    """, unsafe_allow_html=True)

# Sezione Dashboard
def render_dashboard():
    apply_dashboard_styling()
    
    st.markdown("<h1 style='text-align: center; margin-bottom: 30px;'>📊 Dashboard Portafoglio ETF</h1>", unsafe_allow_html=True)
    
    if st.session_state.etf_transactions:
        # Tab per organizzare le sezioni
        tab1, tab2, tab3 = st.tabs(["📈 Riepilogo", "📊 Analisi", "📋 Dettagli"])
        
        # ===== TAB 1: RIEPILOGO =====
        with tab1:
            st.markdown("<div class='section-title'>💰 Statistiche Portafoglio</div>", unsafe_allow_html=True)
            
            # Calcolo metriche
            df_transaction = pd.DataFrame(st.session_state.etf_transactions)
            costo_totale = df_transaction['Costo'].sum() if 'Costo' in df_transaction.columns else 0
            market_value_totale = df_transaction['Market Value'].sum() if 'Market Value' in df_transaction.columns else 0
            crescita_totale = market_value_totale - costo_totale
            rendimento_perc = (crescita_totale / costo_totale * 100) if costo_totale > 0 else 0
            
            # Metriche in colonne
            col1, col2, col3, col4 = st.columns(4, gap="medium")
            with col1:
                st.metric("💵 Totale Investito", f"€{costo_totale:,.2f}", delta=None)
            with col2:
                st.metric("📍 Valore di Mercato", f"€{market_value_totale:,.2f}", 
                         delta=f"€{crescita_totale:,.2f}" if crescita_totale != 0 else None)
            with col3:
                color = "🟢" if crescita_totale >= 0 else "🔴"
                st.metric(f"{color} Guadagno/Perdita", f"€{crescita_totale:,.2f}")
            with col4:
                st.metric("📊 Rendimento %", f"{rendimento_perc:.2f}%", 
                         delta=f"{rendimento_perc:.2f}%" if rendimento_perc != 0 else None)
            
            st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
            
            # Tabella principale con stile
            st.markdown("<div class='section-title'>📍 Posizioni Attuali</div>", unsafe_allow_html=True)
            df_transaction_display = df_transaction.drop(
                columns=[col for col in ["id", "created_at", "updated_at"] if col in df_transaction.columns], 
                errors='ignore'
            )
            st.dataframe(df_transaction_display, use_container_width=True, height=400)
        
        # ===== TAB 2: ANALISI =====
        with tab2:
            st.markdown("<div class='section-title'>🎯 Analisi Portfolio</div>", unsafe_allow_html=True)
            st.markdown("<p style='color: #666; margin-bottom: 20px;'>Distribuzione degli investimenti per diverse dimensioni</p>", unsafe_allow_html=True)
            
            # Grafici in layout 2x2
            col1, col2 = st.columns(2, gap="large")
            
            with col1:
                st.markdown("<div class='subsection-title'>ETF</div>", unsafe_allow_html=True)
                if st.session_state.distribuzione_etf:
                    df_dist_etf = pd.DataFrame(st.session_state.distribuzione_etf)
                    if not df_dist_etf.empty:
                        fig1 = go.Figure(data=[go.Pie(
                            labels=df_dist_etf['ticker'],           
                            values=df_dist_etf['distribuzione_pct'],
                            hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>"
                        )])
                        fig1.update_layout(
                            title="",
                            height=400,
                            showlegend=True,
                            margin=dict(t=10, b=10)
                        )
                        st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                st.markdown("<div class='subsection-title'>Settore</div>", unsafe_allow_html=True)
                if st.session_state.distribuzione_settore:
                    df_dist_settore = pd.DataFrame(st.session_state.distribuzione_settore)
                    if not df_dist_settore.empty:
                        fig2 = go.Figure(data=[go.Pie(
                            labels=df_dist_settore['settore'],
                            values=df_dist_settore['distribuzione_pct'],
                            hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>"
                        )])
                        fig2.update_layout(
                            title="",
                            height=400,
                            showlegend=True,
                            margin=dict(t=10, b=10)
                        )
                        st.plotly_chart(fig2, use_container_width=True)
            
            col3, col4 = st.columns(2, gap="large")
            
            with col3:
                st.markdown("<div class='subsection-title'>Valuta di Mercato</div>", unsafe_allow_html=True)
                if st.session_state.distribuzione_valuta_mercato:
                    df_dist_valuta = pd.DataFrame(st.session_state.distribuzione_valuta_mercato)
                    if not df_dist_valuta.empty:
                        fig3 = go.Figure(data=[go.Pie(
                            labels=df_dist_valuta['valuta_mercato'],
                            values=df_dist_valuta['distribuzione_pct'],
                            hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>"
                        )])
                        fig3.update_layout(
                            title="",
                            height=400,
                            showlegend=True,
                            margin=dict(t=10, b=10)
                        )
                        st.plotly_chart(fig3, use_container_width=True)
            
            with col4:
                st.markdown("<div class='subsection-title'>Area Geografica</div>", unsafe_allow_html=True)
                if st.session_state.distribuzione_area_geografica:
                    df_dist_area = pd.DataFrame(st.session_state.distribuzione_area_geografica)
                    if not df_dist_area.empty:
                        fig4 = go.Figure(data=[go.Pie(
                            labels=df_dist_area['area_geografica'],
                            values=df_dist_area['distribuzione_pct'],
                            hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>"
                        )])
                        fig4.update_layout(
                            title="",
                            height=400,
                            showlegend=True,
                            margin=dict(t=10, b=10)
                        )
                        st.plotly_chart(fig4, use_container_width=True)
        
        # ===== TAB 3: DETTAGLI =====
        with tab3:
            st.markdown("<div class='section-title'>📊 Analisi Dettagliata</div>", unsafe_allow_html=True)
            
            # ETF con migliore e peggiore performance
            col1, col2 = st.columns(2, gap="large")
            
            with col1:
                with st.expander("🏆 Top 3 ETF (Migliori Performance)", expanded=True):
                    df_top_3_etf = pd.DataFrame(st.session_state.top_3_etf)
                    if not df_top_3_etf.empty:
                        st.dataframe(df_top_3_etf, use_container_width=True)
                    else:
                        st.info("Nessun dato disponibile")
            
            with col2:
                with st.expander("📉 Bottom 3 ETF (Peggiori Performance)", expanded=True):
                    df_bottom_3_etf = pd.DataFrame(st.session_state.bottom_3_etf)
                    if not df_bottom_3_etf.empty:
                        st.dataframe(df_bottom_3_etf, use_container_width=True)
                    else:
                        st.info("Nessun dato disponibile")
            
            st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
            
            with st.expander("📈 KPI Portfolio", expanded=False):
                df_portfolio_kpi_etf = pd.DataFrame(st.session_state.kpi_etf)
                if not df_portfolio_kpi_etf.empty:
                    st.dataframe(df_portfolio_kpi_etf, use_container_width=True)
                else:
                    st.info("Nessun dato disponibile")
        
    else:
        # Sezione quando non ci sono transazioni
        st.markdown("<div style='text-align: center; padding: 40px;'>", unsafe_allow_html=True)
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 40px; border-radius: 15px; color: white; text-align: center;'>
            <h2 style='font-size: 2.5em; margin-bottom: 20px;'>👋 Benvenuto!</h2>
            <p style='font-size: 1.2em; margin-bottom: 30px;'>
                Non hai ancora aggiunto transazioni ETF al tuo portafoglio
            </p>
            <p style='font-size: 1em; margin-bottom: 40px; opacity: 0.9;'>
                Aggiungi la tua prima transazione nella sezione <b>"Gestione ETF"</b> per iniziare a tracciare i tuoi investimenti
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div style='margin-top: 40px;'></div>", unsafe_allow_html=True)
        
        # Mostra comunque i dati finti come esempio
        st.markdown("<div class='section-title'>📌 Esempio di Portafoglio</div>", unsafe_allow_html=True)
        st.markdown("<p style='color: #666; margin-bottom: 20px;'>Questo è come apparirà il tuo portafoglio una volta aggiunta la prima transazione</p>", unsafe_allow_html=True)
        
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
        st.dataframe(df_finti, use_container_width=True, height=400)
        
        st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
        
        # Pulsante promozionale
        st.markdown("""
        <div style='background: #f0f4ff; padding: 20px; border-radius: 10px; border-left: 4px solid #667eea;'>
            <h4 style='color: #667eea; margin-top: 0;'>🚀 Inizia Ora</h4>
            <p style='margin: 0; color: #333;'>Vai alla sezione <b>"Gestione ETF"</b> per aggiungere il tuo primo investimento e iniziare a monitorare il tuo portafoglio</p>
        </div>
        """, unsafe_allow_html=True)
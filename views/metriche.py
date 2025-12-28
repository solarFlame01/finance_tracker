import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


# Sezione Metriche (placeholder)
def render_metriche():
    st.header("📐 Metriche Avanzate")
    
    # Due pulsanti affiancati
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("🔄 Aggiorna Storico", use_container_width=True):
            from finance_info import get_all_etf_history
            from database import get_etf_list
            
            etf_list = get_etf_list()
            for etf in etf_list:
                get_all_etf_history(str(etf['etf_ticker']))
            st.success("✅ Storico aggiornato per tutti gli ETF")
    
    with col_btn2:
        if st.button("🔄 Ricalcola Tutte le Correlazioni", use_container_width=True):
            with st.spinner("Calcolo in corso... Questo potrebbe richiedere alcuni minuti"):
                from finance_info import calculate_all_etf_correlations
                stats = calculate_all_etf_correlations()
                st.success(f"✅ Completato: {stats['successful']}/{stats['total_pairs']} correlazioni calcolate")
                if stats['failed'] > 0:
                    with st.expander(f"⚠️ Mostra {stats['failed']} errori"):
                        for error in stats['errors']:
                            st.text(error)
                st.rerun()
    
    from finance_info import calculate_CAGR
    cagr = calculate_CAGR()
    st.metric("CAGR", f"{cagr:.2f}%")
    
    # --- NUOVA SEZIONE: MATRICE DI CORRELAZIONE ---
    st.divider()
    st.subheader("🔗 Matrice di Correlazione ETF")
    
    from database import get_etf_list
    
    # Tabs per separare la matrice dal calcolo singolo
    tab1, tab2 = st.tabs(["📊 Matrice Completa", "🔢 Calcolo Singolo"])
    
    with tab1:
        # Recupera le correlazioni dal database
        try:
            from database import get_etf_correlations
                            
            correlations_data = get_etf_correlations()
            
            if not correlations_data:
                st.info("📭 Nessuna correlazione trovata. Clicca su 'Ricalcola Tutte le Correlazioni' per iniziare.")
            else:
                # Ottieni la data dell'ultimo calcolo
                last_calc_date = pd.to_datetime(correlations_data[0]['calculation_date'])
                st.caption(f"Ultimo aggiornamento: {last_calc_date.strftime('%d/%m/%Y %H:%M')}")
                
                # Costruisci la matrice di correlazione
                etf_list = get_etf_list()
                tickers = sorted([etf['etf_ticker'] for etf in etf_list])
                
                # Inizializza matrice con 1 sulla diagonale
                corr_matrix = pd.DataFrame(np.eye(len(tickers)), 
                                            index=tickers, 
                                            columns=tickers)
                
                # Popola la matrice con i dati dal database
                for corr in correlations_data:
                    etf1 = corr['etf_symbol_1']
                    etf2 = corr['etf_symbol_2']
                    value = corr['correlation_coefficient']
                    
                    # La matrice è simmetrica
                    if etf1 in tickers and etf2 in tickers:
                        corr_matrix.loc[etf1, etf2] = value
                        corr_matrix.loc[etf2, etf1] = value
                
                # Statistiche aggiuntive - PRIMA RIGA (4 metriche base)
                st.subheader("📊 Statistiche Correlazione")
                
                # Estrai solo i valori triangolari superiori (escludendo la diagonale)
                mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
                correlations_values = corr_matrix.where(mask).stack().values
                
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                
                with col_stat1:
                    st.metric("Correlazione Media", f"{np.mean(correlations_values):.3f}")
                with col_stat2:
                    st.metric("Correlazione Massima", f"{np.max(correlations_values):.3f}")
                with col_stat3:
                    st.metric("Correlazione Minima", f"{np.min(correlations_values):.3f}")
                with col_stat4:
                    st.metric("Deviazione Standard", f"{np.std(correlations_values):.3f}")
                
                # SECONDA RIGA - Nuove metriche avanzate
                col_stat5, col_stat6, col_stat7, col_stat8 = st.columns(4)
                
                with col_stat5:
                    median_corr = np.median(correlations_values)
                    st.metric("Mediana Correlazione", f"{median_corr:.3f}",
                             help="Più robusta agli outlier rispetto alla media")
                
                with col_stat6:
                    percentile_25 = np.percentile(correlations_values, 25)
                    st.metric("Percentile 25°", f"{percentile_25:.3f}",
                             help="25% delle correlazioni sono inferiori a questo valore")
                
                with col_stat7:
                    percentile_75 = np.percentile(correlations_values, 75)
                    st.metric("Percentile 75°", f"{percentile_75:.3f}",
                             help="75% delle correlazioni sono inferiori a questo valore")
                
                with col_stat8:
                    high_corr_count = np.sum(correlations_values > 0.7)
                    total_pairs = len(correlations_values)
                    high_corr_pct = (high_corr_count / total_pairs * 100) if total_pairs > 0 else 0
                    st.metric("Coppie Alta Correlazione", f"{high_corr_count}",
                             delta=f"{high_corr_pct:.1f}% del totale",
                             delta_color="inverse",
                             help="Numero di coppie con correlazione > 0.7 (ridotta diversificazione)")
                
                # Interpretazione della diversificazione
                if high_corr_pct > 30:
                    diversification_status = "⚠️ Attenzione: Bassa diversificazione"
                    diversification_color = "warning"
                elif high_corr_pct > 15:
                    diversification_status = "🟡 Diversificazione moderata"
                    diversification_color = "normal"
                else:
                    diversification_status = "✅ Buona diversificazione"
                    diversification_color = "success"
                
                if diversification_color == "warning":
                    st.warning(diversification_status)
                elif diversification_color == "success":
                    st.success(diversification_status)
                else:
                    st.info(diversification_status)
                
                # Matrice di correlazione - RIGA COMPLETA
                fig = go.Figure(data=go.Heatmap(
                    z=corr_matrix.values,
                    x=corr_matrix.columns,
                    y=corr_matrix.index,
                    colorscale='RdYlGn',
                    zmid=0,
                    zmin=-1,
                    zmax=1,
                    text=np.round(corr_matrix.values, 3),
                    texttemplate='%{text}',
                    textfont={"size": 10},
                    colorbar=dict(
                        title="Correlazione",
                        tickvals=[-1, -0.5, 0, 0.5, 1],
                        ticktext=['-1.0', '-0.5', '0.0', '0.5', '1.0']
                    ),
                    hovertemplate='%{y} vs %{x}<br>Correlazione: %{z:.4f}<extra></extra>'
                ))
                
                fig.update_layout(
                    title="Matrice di Correlazione degli ETF",
                    xaxis_title="ETF",
                    yaxis_title="ETF",
                    height=600,
                    xaxis={'side': 'bottom'},
                    yaxis={'autorange': 'reversed'}
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Dettagli correlazioni - DUE COLONNE AFFIANCATE
                corr_df = pd.DataFrame(correlations_data)
                
                col_high, col_low = st.columns(2)
                
                with col_high:
                    st.subheader("🔴 ETF più correlati")
                    top_corr = corr_df.nlargest(5, 'correlation_coefficient')
                    
                    for _, row in top_corr.iterrows():
                        st.text(f"{row['etf_symbol_1']} ↔ {row['etf_symbol_2']}")
                        st.caption(f"Correlazione: {row['correlation_coefficient']:.4f} | Sample: {row['sample_size']}")
                        st.caption(f"Periodo: {row['period_start']} → {row['period_end']}")
                        st.divider()
                
                with col_low:
                    st.subheader("🟢 ETF meno correlati")
                    low_corr = corr_df.nsmallest(5, 'correlation_coefficient')
                    
                    for _, row in low_corr.iterrows():
                        st.text(f"{row['etf_symbol_1']} ↔ {row['etf_symbol_2']}")
                        st.caption(f"Correlazione: {row['correlation_coefficient']:.4f} | Sample: {row['sample_size']}")
                        st.caption(f"Periodo: {row['period_start']} → {row['period_end']}")
                        st.divider()
                
        except Exception as e:
            st.error(f"❌ Errore nel recupero delle correlazioni: {e}")
    
    with tab2:
        st.subheader("🔗 Calcolo Correlazione tra due ETF")
        from finance_info import get_correlation_between_two_etfs
        
        etf_list = [etf['etf_ticker'] for etf in get_etf_list()]
        
        col_corr1, col_corr2 = st.columns(2)
        with col_corr1:
            etf1 = st.selectbox("Seleziona il primo ETF", etf_list, key="etf1_corr")
        with col_corr2:
            etf2 = st.selectbox("Seleziona il secondo ETF", etf_list, key="etf2_corr")

        if st.button("Calcola Correlazione", use_container_width=True):
            if etf1 and etf2:
                if etf1 == etf2:
                    st.warning("Seleziona due ETF diversi per calcolare la correlazione.")
                else:
                    correlation = get_correlation_between_two_etfs(etf1, etf2)
                    if isinstance(correlation, str):
                        st.error(correlation)
                    else:
                        # Interpretazione della correlazione
                        if abs(correlation) > 0.8:
                            interpretation = "Molto forte"
                            color = "🔴"
                        elif abs(correlation) > 0.6:
                            interpretation = "Forte"
                            color = "🟠"
                        elif abs(correlation) > 0.4:
                            interpretation = "Moderata"
                            color = "🟡"
                        else:
                            interpretation = "Debole"
                            color = "🟢"
                        
                        col_m1, col_m2 = st.columns(2)
                        with col_m1:
                            st.metric(f"Correlazione tra {etf1} e {etf2}", f"{correlation:.4f}")
                        with col_m2:
                            st.metric("Interpretazione", f"{color} {interpretation}")
    
    # --- RESTO DELLA DASHBOARD ---
    st.divider()
    
    with st.container():
        st.info("🚧 Sezione in costruzione - Disponibile nella prossima versione")

        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Metriche Pianificate")
            st.markdown("""
            - **Sharpe Ratio**: Misura del rendimento corretto per il rischio
            - **Sortino Ratio**: Focalizzato sulla volatilità al ribasso
            - **Beta vs Benchmark**: Sensibilità al mercato
            - **Alpha**: Rendimento aggiuntivo vs benchmark
            - **R²**: Bontà della correlazione con benchmark
            """)
            
            # Simulazione placeholder
            st.subheader("📊 Simulazione Metrica")
            sharpe_sim = st.slider("Sharpe Ratio simulato", -2.0, 5.0, 1.5, 0.1)
            st.metric("Sharpe Ratio", f"{sharpe_sim:.2f}", 
                     "Buono" if sharpe_sim > 1.0 else "Da migliorare")
        
        with col2:
            st.subheader("📉 Analisi di Rischio")
            st.markdown("""
            - **Value at Risk (VaR)**: Perdita massima attesa
            - **Maximum Drawdown**: Massimo calo storico
            - **Volatilità Annualizzata**: Rischi di prezzo
            - **Correlazione Portafoglio**: Diversificazione
            - **Stress Test**: Performance in scenari critici
            """)
            
            # Grafico placeholder
            st.subheader("📈 Andamento Rischio/Rendimento")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=[0.1, 0.2, 0.3, 0.4, 0.5],
                y=[0.05, 0.08, 0.12, 0.15, 0.18],
                mode='lines+markers',
                name='Portafoglio'
            ))
            fig.update_layout(height=300, title="Frontiera Efficiente")
            st.plotly_chart(fig, use_container_width=True)
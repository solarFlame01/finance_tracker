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
    
    # RIGA 1: CAGR e Sharpe Ratio side by side
    from finance_info import calculate_CAGR
    from database import get_etf_history
    
    cagr = calculate_CAGR()
    
    # Sezione Sharpe Ratio con controllo del risk-free rate
    with st.sidebar:
        st.subheader("⚙️ Impostazioni Sharpe Ratio")
        risk_free_rate = st.slider(
            "Rendimento Risk-Free (Bond 10Y)",
            min_value=0.0,
            max_value=10.0,
            value=3.5,  # Valore attuale medio (Italia/USA)
            step=0.1,
            help="Tasso di rendimento privo di rischio. Per l'Italia: ~3.51%, Per USA: ~4.17%"
        )
    
    # Funzione per calcolare la volatilità allineata al periodo di investimento
    def calculate_portfolio_volatility_aligned():
        """
        Calcola la volatilità del portafoglio allineata al periodo di investimento effettivo.
        
        Usa solo i rendimenti giornalieri nel periodo tra la prima e l'ultima transazione,
        garantendo coerenza con il calcolo del CAGR.
        
        Returns:
            tuple: (volatilità annualizzata in %, volatilità giornaliera in %, 
                    data_inizio, data_fine, giorni_trading)
        """
        try:
            # 1. Determina il periodo di investimento dalle transazioni
            df_transaction = pd.DataFrame(st.session_state.etf_transactions)
            
            if df_transaction.empty or 'Data acquisto' not in df_transaction.columns:
                return None, None, None, None, None
            
            df_transaction['Data acquisto'] = pd.to_datetime(df_transaction['Data acquisto'], errors='coerce')
            data_inizio_portafoglio = df_transaction['Data acquisto'].min()
            data_fine_portafoglio = pd.Timestamp.now()
            
            # 2. Recupera lo storico degli ETF
            all_history_df = pd.DataFrame(get_etf_history())
            
            if all_history_df.empty:
                return None, None, None, None, None
            
            all_history_df['date'] = pd.to_datetime(all_history_df['date'])
            
            # 3. Ottieni i ticker degli ETF nel portafoglio
            portfolio_tickers = df_transaction['Ticker'].unique()
            
            # 4. Filtra solo gli ETF del portafoglio e il periodo di investimento
            portfolio_history = all_history_df[
                (all_history_df['ticker'].isin(portfolio_tickers)) &
                (all_history_df['date'] >= data_inizio_portafoglio) &
                (all_history_df['date'] <= data_fine_portafoglio)
            ].copy()
            
            if portfolio_history.empty:
                return None, None, None, None, None
            
            portfolio_history = portfolio_history.sort_values('date')
            
            # 5. Calcola rendimenti giornalieri per ogni ETF nel periodo
            daily_returns_list = []
            
            for ticker in portfolio_tickers:
                ticker_data = portfolio_history[portfolio_history['ticker'] == ticker].copy()
                
                if len(ticker_data) < 2:
                    continue
                
                ticker_data = ticker_data.sort_values('date')
                ticker_data['daily_return'] = ticker_data['close'].pct_change()
                
                # Rimuovi NaN e aggiungi alla lista
                returns = ticker_data['daily_return'].dropna()
                daily_returns_list.extend(returns.values)
            
            if len(daily_returns_list) == 0:
                return None, None, None, None, None
            
            # 6. Converti in array e rimuovi eventuali NaN residui
            all_daily_returns = np.array(daily_returns_list)
            all_daily_returns = all_daily_returns[~np.isnan(all_daily_returns)]
            
            if len(all_daily_returns) == 0:
                return None, None, None, None, None
            
            # 7. Calcola volatilità
            daily_volatility = np.std(all_daily_returns)
            annual_volatility = daily_volatility * np.sqrt(252)
            
            # 8. Conta i giorni di trading effettivi
            giorni_trading = len(portfolio_history['date'].unique())
            
            return (
                annual_volatility * 100,  # Percentuale
                daily_volatility * 100,   # Percentuale
                data_inizio_portafoglio,
                data_fine_portafoglio,
                giorni_trading
            )
            
        except Exception as e:
            st.error(f"Errore nel calcolo della volatilità: {e}")
            return None, None, None, None, None
    
    # Calcolo Sharpe Ratio allineato
    def calculate_sharpe_ratio_aligned(risk_free_rate):
        """
        Calcola lo Sharpe Ratio usando volatilità allineata al periodo di investimento.
        
        Args:
            risk_free_rate (float): Tasso risk-free annualizzato
        
        Returns:
            float: Lo Sharpe Ratio annualizzato
        """
        try:
            # Usa la volatilità allineata
            annual_vol, _, _, _, _ = calculate_portfolio_volatility_aligned()
            
            if annual_vol is None or cagr is None:
                return None
            
            # Converti volatilità da percentuale a decimale
            annual_volatility = annual_vol / 100
            portfolio_return = cagr / 100
            
            # Sharpe Ratio = (Rp - Rf) / σp
            sharpe_ratio = (portfolio_return - (risk_free_rate / 100)) / annual_volatility if annual_volatility > 0 else 0
            
            return sharpe_ratio
            
        except Exception as e:
            st.error(f"Errore nel calcolo dello Sharpe Ratio: {e}")
            return None
    
    # Calcolo delle metriche
    sharpe = calculate_sharpe_ratio_aligned(risk_free_rate)
    annual_vol, daily_vol, data_inizio, data_fine, giorni_trading = calculate_portfolio_volatility_aligned()
    
    # Interpretazione dello Sharpe Ratio
    def interpret_sharpe_ratio(sharpe):
        if sharpe is None:
            return "N/A", "normal"
        elif sharpe < 1.0:
            return "Sub-Par", "inverse"
        elif sharpe < 2.0:
            return "Accettabile", "normal"
        elif sharpe < 3.0:
            return "Buono", "off"
        else:
            return "Eccezionale", "off"
    
    # Interpretazione della volatilità
    def interpret_volatility(vol):
        if vol is None:
            return "N/A", "normal"
        elif vol < 12:
            return "Bassa", "off"
        elif vol < 18:
            return "Moderata", "normal"
        elif vol < 25:
            return "Alta", "inverse"
        else:
            return "Molto Alta", "inverse"
    
    interpretation_sharpe, delta_color_sharpe = interpret_sharpe_ratio(sharpe)
    interpretation_vol, delta_color_vol = interpret_volatility(annual_vol)
    
    # Visualizza CAGR e Sharpe Ratio nella stessa riga
    col_metrics1, col_metrics2 = st.columns(2)
    
    with col_metrics1:
        st.metric("CAGR", f"{cagr:.2f}%")
    
    with col_metrics2:
        if sharpe is not None:
            st.metric(
                "Sharpe Ratio",
                f"{sharpe:.3f}",
                delta=interpretation_sharpe,
                delta_color=delta_color_sharpe,
                help=f"Rendimento aggiustato per il rischio (Risk-free: {risk_free_rate:.2f}%)\n\n"
                     f"< 1.0: Sub-Par | 1.0-2.0: Accettabile | 2.0-3.0: Buono | > 3.0: Eccezionale"
            )
        else:
            st.metric("Sharpe Ratio", "N/A", help="Dati insufficienti per il calcolo")
    
    # RIGA 2: Volatilità del portafoglio
    col_metrics3, col_metrics4 = st.columns(2)
    
    with col_metrics3:
        if annual_vol is not None:
            st.metric(
                "Volatilità Annualizzata",
                f"{annual_vol:.2f}%",
                delta=interpretation_vol,
                delta_color=delta_color_vol,
                help="Deviazione standard dei rendimenti annualizzati nel periodo di investimento\n\n"
                     "< 12%: Bassa | 12-18%: Moderata | 18-25%: Alta | > 25%: Molto Alta\n\n"
                     "Benchmark: S&P 500 ~15-20%, Portafogli diversificati ~12-18%"
            )
        else:
            st.metric("Volatilità Annualizzata", "N/A", help="Dati insufficienti per il calcolo")
    
    with col_metrics4:
        if daily_vol is not None:
            st.metric(
                "Volatilità Giornaliera",
                f"{daily_vol:.3f}%",
                help="Deviazione standard dei rendimenti giornalieri nel periodo di investimento"
            )
        else:
            st.metric("Volatilità Giornaliera", "N/A", help="Dati insufficienti per il calcolo")
    
    # Spiegazione delle formule
    with st.expander("📖 Formule e Interpretazioni"):
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            st.markdown("""
            **Sharpe Ratio = (Rp - Rf) / σp**
            
            Dove:
            - **Rp** = Rendimento del portafoglio (CAGR)
            - **Rf** = Tasso risk-free (Bond 10 anni)
            - **σp** = Volatilità del portafoglio
            
            **Interpretazione:**
            - **< 1.0**: Sub-par
            - **1.0 - 2.0**: Accettabile
            - **2.0 - 3.0**: Buono
            - **> 3.0**: Eccezionale
            """)
        
        with col_exp2:
            st.markdown("""
            **Volatilità = σ × √252**
            
            Dove:
            - **σ** = Deviazione standard rendimenti giornalieri
            - **252** = Giorni di trading in un anno
            
            **Benchmark:**
            - **Bond governativi**: 2-5%
            - **S&P 500**: 15-20%
            - **Portafogli diversificati**: 12-18%
            - **Mercati emergenti**: 20-25%
            - **Portafogli concentrati**: > 25%
            """)
        
        # Analisi dettagliata se entrambi i valori sono disponibili
        if annual_vol is not None and sharpe is not None and data_inizio is not None:
            st.divider()
            st.markdown("### 🔍 Analisi Portafoglio")
            
            excess_return = cagr - risk_free_rate
            giorni_totali = (data_fine - data_inizio).days
            anni_investimento = giorni_totali / 365.25
            
            col_detail1, col_detail2 = st.columns(2)
            
            with col_detail1:
                st.markdown(f"""
                **Periodo di Investimento:**
                - Data inizio: **{data_inizio.date()}**
                - Data fine: **{data_fine.date()}**
                - Giorni totali: **{giorni_totali}**
                - Anni: **{anni_investimento:.2f}**
                - Giorni di trading: **{giorni_trading}**
                """)
            
            with col_detail2:
                st.markdown(f"""
                **Componenti Sharpe Ratio:**
                - CAGR: **{cagr:.2f}%**
                - Risk-Free: **{risk_free_rate:.2f}%**
                - Excess Return: **{excess_return:.2f}%**
                - Volatilità: **{annual_vol:.2f}%**
                - **Sharpe: {sharpe:.3f}**
                """)
            
            # Suggerimenti basati sui valori
            if annual_vol > 20:
                st.warning(f"⚠️ Volatilità alta ({annual_vol:.2f}%). Considera maggiore diversificazione.")
            
            if sharpe < 0.5 and excess_return > 0:
                st.warning(f"⚠️ Sharpe basso ({sharpe:.3f}) nonostante rendimento positivo. Problema: volatilità eccessiva.")
            elif sharpe >= 1.0:
                st.success(f"✅ Sharpe {sharpe:.3f}: buon equilibrio rischio/rendimento.")
    
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
                
                # Rimuovi esplicitamente i valori NaN per evitare errori nei calcoli di NumPy
                correlations_values = correlations_values[~np.isnan(correlations_values)]
                
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
            - **Sortino Ratio**: Focalizzato sulla volatilità al ribasso
            - **Beta vs Benchmark**: Sensibilità al mercato
            - **Alpha**: Rendimento aggiuntivo vs benchmark
            - **R²**: Bontà della correlazione con benchmark
            """)
            
        with col2:
            st.subheader("📉 Analisi di Rischio")
            st.markdown("""
            - **Value at Risk (VaR)**: Perdita massima attesa
            - **Maximum Drawdown**: Massimo calo storico
            - **Stress Test**: Performance in scenari critici
            """)
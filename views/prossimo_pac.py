import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from math import floor


def render_prossimo_pac():
    st.header("💼 Prossimo PAC")
    st.markdown("Calcola quante quote acquistare per mantenere la distribuzione target del portafoglio.")

    distribuzione_etf = st.session_state.get('distribuzione_etf', [])
    prezzo_medio = st.session_state.get('prezzo_medio_acquisto', [])

    if not distribuzione_etf or not prezzo_medio:
        st.warning("Dati del portafoglio non disponibili. Assicurati di avere ETF in portafoglio.")
        return

    df_prezzi = pd.DataFrame(prezzo_medio)
    df_dist = pd.DataFrame(distribuzione_etf)

    prezzi_dict = dict(zip(df_prezzi['ticker'], df_prezzi['price']))

    budget = st.number_input(
        "Budget disponibile (€)",
        min_value=0.0,
        value=500.0,
        step=50.0,
        format="%.2f"
    )

    st.subheader("Distribuzione Target (%)")
    st.caption("Modifica le percentuali target per ogni ETF. La somma deve essere 100%.")

    target_data = []
    for _, row in df_dist.iterrows():
        target_data.append({
            'Ticker': row['ticker'],
            'Target %': float(row['distribuzione_pct'])
        })

    df_target = pd.DataFrame(target_data)

    edited_df = st.data_editor(
        df_target,
        column_config={
            'Ticker': st.column_config.TextColumn('Ticker', disabled=True),
            'Target %': st.column_config.NumberColumn('Target %', min_value=0.0, max_value=100.0, step=0.1, format="%.1f")
        },
        hide_index=True,
        use_container_width=True
    )

    somma_target = edited_df['Target %'].sum()
    if abs(somma_target - 100.0) > 0.5:
        st.warning(f"La somma delle percentuali target è {somma_target:.1f}%. Dovrebbe essere 100%.")

    if st.button("Calcola Allocazione", type="primary", use_container_width=True):
        if budget <= 0:
            st.error("Inserisci un budget maggiore di 0.")
            return

        tickers = edited_df['Ticker'].tolist()
        targets = dict(zip(edited_df['Ticker'], edited_df['Target %']))

        tickers_validi = [t for t in tickers if t in prezzi_dict and prezzi_dict[t] > 0]

        if not tickers_validi:
            st.error("Nessun ETF con prezzo disponibile.")
            return

        allocazione = {t: 0 for t in tickers_validi}
        budget_rimanente = budget

        # Fase 1: allocazione proporzionale
        for t in tickers_validi:
            importo_ideale = budget * (targets[t] / 100.0)
            quote = floor(importo_ideale / prezzi_dict[t])
            allocazione[t] = quote
            budget_rimanente -= quote * prezzi_dict[t]

        # Fase 2: allocazione residuo (greedy)
        while budget_rimanente > 0:
            candidati = [t for t in tickers_validi if prezzi_dict[t] <= budget_rimanente]
            if not candidati:
                break

            speso_totale = budget - budget_rimanente
            if speso_totale == 0:
                best = max(candidati, key=lambda t: targets[t])
            else:
                best = max(candidati, key=lambda t: targets[t] - (allocazione[t] * prezzi_dict[t] / (speso_totale + prezzi_dict[t]) * 100))

            allocazione[best] += 1
            budget_rimanente -= prezzi_dict[best]

        # Risultati
        budget_utilizzato = budget - budget_rimanente

        risultati = []
        for t in tickers_validi:
            costo = allocazione[t] * prezzi_dict[t]
            pct = (costo / budget_utilizzato * 100) if budget_utilizzato > 0 else 0
            risultati.append({
                'Ticker': t,
                'Quote': int(allocazione[t]),
                'Prezzo unitario (€)': round(prezzi_dict[t], 2),
                'Costo (€)': round(costo, 2),
                '% Allocata': round(pct, 1),
                'Target %': targets[t]
            })

        df_risultati = pd.DataFrame(risultati)
        df_risultati = df_risultati[df_risultati['Quote'] > 0]

        st.divider()

        # Riepilogo
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Budget Totale", f"€{budget:,.2f}")
        with col2:
            st.metric("Budget Utilizzato", f"€{budget_utilizzato:,.2f}")
        with col3:
            st.metric("Budget Residuo", f"€{budget_rimanente:,.2f}")

        st.subheader("ETF da acquistare")
        if df_risultati.empty:
            st.info("Il budget non è sufficiente per acquistare nessuna quota intera.")
        else:
            st.dataframe(
                df_risultati,
                hide_index=True,
                use_container_width=True,
                column_config={
                    'Costo (€)': st.column_config.NumberColumn(format="%.2f"),
                    'Prezzo unitario (€)': st.column_config.NumberColumn(format="%.2f"),
                    '% Allocata': st.column_config.NumberColumn(format="%.1f"),
                    'Target %': st.column_config.NumberColumn(format="%.1f")
                }
            )

            # Grafico comparativo
            st.subheader("Distribuzione: Target vs Risultante")
            col_chart1, col_chart2 = st.columns(2)

            with col_chart1:
                fig_target = go.Figure(data=[go.Pie(
                    labels=edited_df['Ticker'],
                    values=edited_df['Target %'],
                    textinfo='label+percent',
                    textposition='auto'
                )])
                fig_target.update_layout(title="Target", height=350, margin=dict(t=40, b=10))
                st.plotly_chart(fig_target, use_container_width=True)

            with col_chart2:
                df_chart = pd.DataFrame(risultati)
                fig_result = go.Figure(data=[go.Pie(
                    labels=df_chart['Ticker'],
                    values=df_chart['Costo (€)'],
                    textinfo='label+percent',
                    textposition='auto'
                )])
                fig_result.update_layout(title="Risultante", height=350, margin=dict(t=40, b=10))
                st.plotly_chart(fig_result, use_container_width=True)

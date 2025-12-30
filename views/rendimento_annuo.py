import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta


# Sezione Rendimento Portafoglio
def render_rendimento_annuo():
    st.header("📅 Performance Portafoglio")
    
    # Recupera dati da session_state
    if "rendimento_annuo" not in st.session_state or not st.session_state.rendimento_annuo:
        st.warning("⚠️ Nessun dato di rendimento disponibile. Carica i dati della vista v_portafoglio_rendimento_annuo.")
        return
    
    # Converti in DataFrame
    df_portafoglio = pd.DataFrame(st.session_state.rendimento_annuo)
    
    # Verifica colonne richieste
    required_cols = [
        "prima_operazione_portafoglio",
        "costo_investito_tot_eur",
        "market_value_tot_attuale",
        "guadagno_tot_eur",
        "rendimento_annuo_pct"
    ]
    missing_cols = [col for col in required_cols if col not in df_portafoglio.columns]
    
    if missing_cols:
        st.error(f"❌ Colonne mancanti: {', '.join(missing_cols)}")
        st.write("Colonne disponibili:", df_portafoglio.columns.tolist())
        return
    
    # Estrai primo (e unico) record
    row = df_portafoglio.iloc[0]
    
    # Conversione tipi
    data_inizio = pd.to_datetime(row["prima_operazione_portafoglio"])
    costo_investito = float(row["costo_investito_tot_eur"])
    valore_attuale = float(row["market_value_tot_attuale"])
    guadagno_totale = float(row["guadagno_tot_eur"])
    rendimento_annuo = float(row["rendimento_annuo_pct"])
    giorni_investimento = int(row.get("giorni_investimento", (datetime.now().date() - data_inizio.date()).days))
    
    # Calcoli aggiuntivi
    anni_investimento = giorni_investimento / 365.25
    guadagno_pct = (guadagno_totale / costo_investito * 100) if costo_investito > 0 else 0
    
    # Layout principale
    col1, col2, col3 = st.columns([1.2, 1, 1])
    
    with col1:
        st.subheader("📋 Dettagli Portafoglio")
        
        # Tabella riepilogativa
        dettagli_df = pd.DataFrame({
            "Metrica": [
                "Data Inizio Investimento",
                "Giorni Investimento",
                "Anni Investimento",
                "Importo Investito",
                "Valore Attuale",
                "Guadagno Totale",
                "Guadagno %",
                "Rendimento Annuo (CAGR)"
            ],
            "Valore": [
                data_inizio.strftime("%d/%m/%Y"),
                f"{giorni_investimento:,}",
                f"{anni_investimento:.2f}",
                f"€ {costo_investito:,.2f}",
                f"€ {valore_attuale:,.2f}",
                f"€ {guadagno_totale:,.2f}",
                f"{guadagno_pct:.2f}%",
                f"{rendimento_annuo:.2f}%"
            ]
        })
        
        st.dataframe(
            dettagli_df,
            use_container_width=True,
            hide_index=True,
            height="auto"
        )
    
    with col2:
        st.subheader("💰 Composizione Valore")
        
        # Torta: Costo Investito vs Guadagno
        if guadagno_totale >= 0:
            colori = ["#1f77b4", "#2ca02c"]  # Blu investito, Verde guadagno
            etichette = [
                f"Investito\n€ {costo_investito:,.0f}",
                f"Guadagno\n€ {guadagno_totale:,.0f}"
            ]
        else:
            colori = ["#1f77b4", "#d62728"]  # Blu investito, Rosso perdita
            etichette = [
                f"Investito\n€ {costo_investito:,.0f}",
                f"Perdita\n€ {guadagno_totale:,.0f}"
            ]
        
        fig_pie = go.Figure(data=[
            go.Pie(
                values=[costo_investito, abs(guadagno_totale)],
                labels=etichette,
                marker=dict(colors=colori),
                textposition="inside",
                textinfo="label+percent",
                hovertemplate="<b>%{label}</b><br>€ %{value:,.0f}<extra></extra>"
            )
        ])
        
        fig_pie.update_layout(
            height=350,
            showlegend=False,
            margin=dict(t=20, b=20, l=20, r=20)
        )
        
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with col3:
        st.subheader("📊 Rendimento Annuo")

        # Estrai solo l'anno dalla data
        df_portafoglio["anno"] = pd.to_datetime(df_portafoglio["prima_operazione_portafoglio"]).dt.year.astype(str)
        df_portafoglio["rendimento_annuo_pct"] = pd.to_numeric(
            df_portafoglio["rendimento_annuo_pct"], errors="coerce"
        )
        
        # Ordina per anno
        df_portafoglio = df_portafoglio.sort_values("anno", ascending=True)
        
        # Colori dinamici: verde per positivo, rosso per negativo
        colori = [
            "#2ca02c" if r >= 0 else "#d62728" 
            for r in df_portafoglio["rendimento_annuo_pct"]
        ]
        
        fig_bars = go.Figure(data=[
            go.Bar(
                x=df_portafoglio["anno"],
                y=df_portafoglio["rendimento_annuo_pct"],
                marker=dict(color=colori),
                text=[f"{r:.2f}%" for r in df_portafoglio["rendimento_annuo_pct"]],
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Rendimento: %{y:.2f}%<extra></extra>"
            )
        ])
        
        fig_bars.add_hline(
            y=0,
            line_dash="dash",
            line_color="gray",
            opacity=0.5
        )
        
        fig_bars.update_layout(
            height=350,
            yaxis_title="Rendimento %",
            xaxis_title="Anno",
            showlegend=False,
            hovermode="x unified",
            template="plotly_white",
            margin=dict(b=50, t=50, l=50, r=50)
        )
        
        st.plotly_chart(fig_bars, use_container_width=True)

    # Statistiche principali
    st.subheader("📊 Statistiche Principali")
    
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    
    with stat_col1:
        delta_color = "normal" if guadagno_totale >= 0 else "inverse"
        st.metric(
            "Guadagno Totale",
            f"€ {guadagno_totale:,.2f}",
            delta=f"{guadagno_pct:.2f}%",
            delta_color=delta_color
        )
    
    with stat_col2:
        st.metric(
            "Rendimento Annuo",
            f"{rendimento_annuo:.2f}%",
            delta=f"CAGR",
            delta_color="off"
        )
    
    with stat_col3:
        st.metric(
            "Valore Attuale",
            f"€ {valore_attuale:,.2f}",
            delta=f"+€ {guadagno_totale:,.2f}",
            delta_color="normal" if guadagno_totale >= 0 else "inverse"
        )
    
    with stat_col4:
        st.metric(
            "Periodo Investimento",
            f"{anni_investimento:.1f} anni",
            delta=f"{giorni_investimento} giorni",
            delta_color="off"
        )
        
    # Informazioni dettagliate
    with st.expander("ℹ️ Spiegazione delle Metriche"):
        st.markdown("""
        **Guadagno Totale**: Differenza tra il valore attuale e l'importo investito.
        
        **Guadagno %**: Rendimento semplice calcolato come (Guadagno / Investito) × 100.
        
        **Rendimento Annuo (CAGR)**: 
        - Compound Annual Growth Rate
        - Rappresenta il rendimento medio annualizzato dal primo investimento ad oggi
        - Utile per confrontare con indici di mercato e altre strategie
        
        **Giorni/Anni di Investimento**: Tempo totale dal primo acquisto ad oggi.
        """)


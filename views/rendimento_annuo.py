import streamlit as st
import pandas as pd
import plotly.graph_objects as go


def _carica_rendimento_annuo():
    """Restituisce i dati annuali (lista di dict) dalla vista v_portafoglio_rendimento_annuo."""
    dati = st.session_state.get("rendimento_annuo")
    if dati:
        return dati
    try:
        from database import get_rendimento_annuo
        dati = get_rendimento_annuo()
        st.session_state.rendimento_annuo = dati
        return dati
    except Exception:
        return []


def _carica_kpi_portafoglio():
    """Restituisce le KPI per ticker (lista di dict) dalla vista v_portfolio_ticker_kpi.

    Usato per calcolare il TOTALE reale del portafoglio (costo, valore, guadagno),
    perche' la vista annuale non fornisce un valore attuale affidabile per l'anno in corso.
    """
    dati = st.session_state.get("kpi_etf")
    if dati:
        return dati
    try:
        from database import get_portfolio_kpi_etf
        dati = get_portfolio_kpi_etf()
        st.session_state.kpi_etf = dati
        return dati
    except Exception:
        return []


# Sezione Rendimento Portafoglio
def render_rendimento_annuo():
    st.header("📅 Performance Portafoglio")

    # --- Dati annuali (dettaglio per anno) ---
    dati_annuali = _carica_rendimento_annuo()
    if not dati_annuali:
        st.warning("⚠️ Nessun dato annuale disponibile dalla vista v_portafoglio_rendimento_annuo.")
        return

    df = pd.DataFrame(dati_annuali)
    df.columns = [str(c).strip().lower() for c in df.columns]

    required_cols = [
        "anno",
        "costo_acquisti_anno_eur",
        "valore_fine_anno_eur",
        "guadagno_anno_eur",
        "rendimento_annuo_pct",
    ]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"❌ Colonne mancanti: {', '.join(missing_cols)}")
        st.write("Colonne disponibili:", df.columns.tolist())
        return

    # Conversione tipi
    df["anno"] = pd.to_numeric(df["anno"], errors="coerce").astype("Int64")
    for col in required_cols[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["anno"]).sort_values("anno").reset_index(drop=True)

    if df.empty:
        st.warning("⚠️ Nessun anno valido nei dati di rendimento.")
        return

    # --- TOTALE reale del portafoglio dalle KPI per ticker ---
    kpi = _carica_kpi_portafoglio()
    if kpi:
        df_kpi = pd.DataFrame(kpi)
        costo_investito = float(pd.to_numeric(df_kpi["costo_investito_eur"], errors="coerce").sum())
        valore_attuale = float(pd.to_numeric(df_kpi["market_value_attuale"], errors="coerce").sum())
        guadagno_totale = valore_attuale - costo_investito
        fonte_totale = "posizioni attuali (v_portfolio_ticker_kpi)"
    else:
        # Fallback: usa i dati annuali (meno affidabile per l'anno in corso)
        costo_investito = float(df["costo_acquisti_anno_eur"].sum())
        guadagno_totale = float(df["guadagno_anno_eur"].sum())
        valore_attuale = costo_investito + guadagno_totale
        fonte_totale = "somma dati annuali"

    rendimento_totale_pct = (guadagno_totale / costo_investito * 100) if costo_investito > 0 else 0.0

    primo_anno = int(df["anno"].min())
    ultimo_anno = int(df["anno"].max())
    numero_anni = ultimo_anno - primo_anno + 1

    # =====================================================================
    # RIGA 1 - Totali del portafoglio (obiettivo: rendimento annuo totale)
    # =====================================================================
    st.subheader("🎯 Rendimento Totale Portafoglio")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(
            "Rendimento Totale",
            f"{rendimento_totale_pct:.2f}%",
            delta=f"€ {guadagno_totale:,.2f}",
            delta_color="normal" if guadagno_totale >= 0 else "inverse",
        )
    with m2:
        st.metric("Importo Investito", f"€ {costo_investito:,.2f}")
    with m3:
        st.metric(
            "Valore Attuale",
            f"€ {valore_attuale:,.2f}",
            delta=f"{'+' if guadagno_totale >= 0 else ''}€ {guadagno_totale:,.2f}",
            delta_color="normal" if guadagno_totale >= 0 else "inverse",
        )
    with m4:
        st.metric("Periodo", f"{numero_anni} anni", delta=f"{primo_anno}–{ultimo_anno}", delta_color="off")

    st.caption(f"Totale calcolato da: {fonte_totale}")

    st.divider()

    # =====================================================================
    # RIGA 2 - Dettaglio annuale + grafici
    # =====================================================================
    col1, col2, col3 = st.columns([1.3, 1, 1.2])

    with col1:
        st.subheader("📋 Dettaglio Annuale")
        dettagli_df = pd.DataFrame({
            "Anno": df["anno"].astype(int).astype(str),
            "Acquisti": df["costo_acquisti_anno_eur"].map(lambda v: f"€ {v:,.2f}"),
            "Valore Fine Anno": df["valore_fine_anno_eur"].map(lambda v: f"€ {v:,.2f}"),
            "Guadagno": df["guadagno_anno_eur"].map(lambda v: f"€ {v:,.2f}"),
            "Rend. %": df["rendimento_annuo_pct"].map(lambda v: f"{v:,.2f}%"),
        })
        st.dataframe(dettagli_df, use_container_width=True, hide_index=True)

    with col2:
        st.subheader("💰 Composizione Valore")
        if guadagno_totale >= 0:
            colori = ["#1f77b4", "#2ca02c"]
            etichette = [f"Investito € {costo_investito:,.0f}", f"Guadagno € {guadagno_totale:,.0f}"]
        else:
            colori = ["#1f77b4", "#d62728"]
            etichette = [f"Investito € {costo_investito:,.0f}", f"Perdita € {guadagno_totale:,.0f}"]

        fig_pie = go.Figure(data=[
            go.Pie(
                values=[costo_investito, abs(guadagno_totale)],
                labels=etichette,
                marker=dict(colors=colori),
                textposition="inside",
                textinfo="label+percent",
                hovertemplate="<b>%{label}</b><br>€ %{value:,.0f}<extra></extra>",
            )
        ])
        fig_pie.update_layout(height=350, showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col3:
        st.subheader("📊 Rendimento per Anno")
        anni = df["anno"].astype(int).astype(str)
        rendimenti = df["rendimento_annuo_pct"].fillna(0)
        colori_bar = ["#2ca02c" if r >= 0 else "#d62728" for r in rendimenti]

        fig_bars = go.Figure(data=[
            go.Bar(
                x=anni,
                y=rendimenti,
                marker=dict(color=colori_bar),
                text=[f"{r:.2f}%" for r in rendimenti],
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Rendimento: %{y:.2f}%<extra></extra>",
            )
        ])
        fig_bars.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig_bars.update_layout(
            height=350,
            yaxis_title="Rendimento %",
            xaxis_title="Anno",
            showlegend=False,
            hovermode="x unified",
            template="plotly_white",
            margin=dict(b=50, t=50, l=50, r=50),
        )
        st.plotly_chart(fig_bars, use_container_width=True)

    # =====================================================================
    # Note esplicative
    # =====================================================================
    with st.expander("ℹ️ Come vengono calcolate le metriche"):
        st.markdown("""
        **Rendimento Totale**: guadagno complessivo sul portafoglio attualmente detenuto,
        calcolato come *(Valore Attuale − Importo Investito) / Importo Investito*.
        Usa il valore di mercato reale delle posizioni (vista `v_portfolio_ticker_kpi`),
        non il valore di fine anno della vista annuale.

        **Dettaglio Annuale**: per ogni anno mostra gli acquisti effettuati,
        il valore di fine anno, il guadagno e il rendimento percentuale
        (vista `v_portafoglio_rendimento_annuo`).

        **Nota sull'anno in corso**: se l'anno corrente non ha ancora un valore di fine
        anno valorizzato, la sua riga puo' mostrare valore 0 e rendimento -100%. Questo
        NON influisce sul Rendimento Totale, che si basa sulle posizioni attuali.
        """)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

MESI_IT = {
    1: "gen", 2: "feb", 3: "mar", 4: "apr", 5: "mag", 6: "giu",
    7: "lug", 8: "ago", 9: "set", 10: "ott", 11: "nov", 12: "dic",
}

MESI_IT_FULL = {
    1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile", 5: "maggio",
    6: "giugno", 7: "luglio", 8: "agosto", 9: "settembre", 10: "ottobre",
    11: "novembre", 12: "dicembre",
}


# ---------------------------------------------------------------------------
# Caricamento dati (con cache in session_state)
# ---------------------------------------------------------------------------
def _carica(chiave_state, nome_funzione):
    """Carica dati da database.py con cache in session_state."""
    dati = st.session_state.get(chiave_state)
    if dati:
        return dati
    try:
        import database
        dati = getattr(database, nome_funzione)()
        st.session_state[chiave_state] = dati
        return dati
    except Exception:
        return []


def _carica_rendimento_mensile():
    return _carica("rendimento_mensile", "get_rendimento_mensile")


def _carica_rendimento_cumulato():
    return _carica("rendimento_cumulato", "get_rendimento_cumulato")


def _carica_rendimento_annuo():
    return _carica("rendimento_annuo", "get_rendimento_annuo")


# ---------------------------------------------------------------------------
# Grafico principale stile "Performance" (barre mensili + linea cumulata YTD)
# ---------------------------------------------------------------------------
def _grafico_performance(df_mese_anno: pd.DataFrame, anno: int):
    """Barre = rendimento mensile; linea = rendimento cumulato YTD.

    Mostra sempre tutti e 12 i mesi dell'anno (gen..dic), con buchi
    per i mesi senza dati, come nel riferimento Bloomberg.
    """
    base = pd.DataFrame({"mese": range(1, 13)})
    df = base.merge(df_mese_anno, on="mese", how="left")
    df["label"] = df["mese"].map(lambda m: f"{MESI_IT[m]}'{str(anno)[2:]}")

    fig = go.Figure()

    # Barre: rendimento mensile
    colori = [
        "#1f77b4" if (pd.notna(v) and v >= 0) else "#c0392b"
        for v in df["rendimento_mensile_pct"]
    ]
    fig.add_trace(go.Bar(
        x=df["label"],
        y=df["rendimento_mensile_pct"],
        name="Rendimento mensile",
        marker=dict(color=colori),
        hovertemplate="<b>%{x}</b><br>Mese: %{y:.2f}%<extra></extra>",
    ))

    # Linea: rendimento cumulato da inizio anno
    fig.add_trace(go.Scatter(
        x=df["label"],
        y=df["rendimento_cumulato_ytd_pct"],
        name="Cumulato YTD",
        mode="lines+markers",
        line=dict(color="#d62728", width=2),
        marker=dict(symbol="square", size=8, color="#d62728"),
        connectgaps=True,
        hovertemplate="<b>%{x}</b><br>Cumulato: %{y:.2f}%<extra></extra>",
    ))

    fig.add_hline(y=0, line_color="#888", line_width=1)
    fig.update_layout(
        title=f"Performance {anno}",
        height=420,
        template="plotly_white",
        yaxis=dict(title="", ticksuffix="%", zeroline=True),
        xaxis=dict(title=""),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40, l=50, r=30),
        hovermode="x unified",
    )
    return fig


# ---------------------------------------------------------------------------
# Vista principale
# ---------------------------------------------------------------------------
def _aggiorna_storico_prezzi_ui():
    """Scarica lo storico prezzi aggiornato e ricarica i dati in session_state."""
    try:
        from aggiorna_storico_prezzi import aggiorna_storico
    except Exception as e:
        st.error(f"Impossibile avviare l'aggiornamento: {e}")
        return

    barra = st.progress(0.0, text="Avvio aggiornamento storico prezzi...")

    def _cb(i, tot, ticker, righe):
        barra.progress(i / tot, text=f"[{i}/{tot}] {ticker}: {righe} righe")

    with st.spinner("Scarico i prezzi da Yahoo Finance..."):
        res = aggiorna_storico(progress_cb=_cb)

    barra.empty()

    # Invalida la cache delle viste di rendimento: verranno ricaricate al rerun
    for chiave in ("rendimento_mensile", "rendimento_cumulato", "rendimento_annuo"):
        st.session_state.pop(chiave, None)

    if res["ko"] == 0:
        st.success(f"✅ Storico aggiornato: {res['ok']}/{res['totale']} ticker.")
    else:
        st.warning(
            f"⚠️ Aggiornamento parziale: {res['ok']} ok, {res['ko']} falliti "
            f"su {res['totale']}."
        )
    st.rerun()


def render_rendimento_annuo():
    st.header("📈 Performance Portafoglio")

    col_titolo, col_btn = st.columns([3, 1])
    with col_btn:
        if st.button("🔄 Aggiorna storico prezzi", use_container_width=True,
                     help="Scarica da Yahoo Finance lo storico prezzi aggiornato "
                          "per gli ETF in portafoglio e ricalcola i rendimenti."):
            _aggiorna_storico_prezzi_ui()

    df_mensile_raw = _carica_rendimento_mensile()
    if not df_mensile_raw:
        st.warning(
            "⚠️ Nessun dato mensile disponibile dalla vista "
            "`v_portafoglio_rendimento_mensile`. Verifica di avere lo storico "
            "prezzi (`etf_price_history`) e le transazioni popolati."
        )
        return

    dfm = pd.DataFrame(df_mensile_raw)
    for col in ["anno", "mese"]:
        dfm[col] = pd.to_numeric(dfm[col], errors="coerce").astype("Int64")
    for col in ["valore_fine_mese_eur", "flusso_netto_eur",
                "rendimento_mensile_pct", "rendimento_cumulato_ytd_pct"]:
        dfm[col] = pd.to_numeric(dfm[col], errors="coerce")
    dfm = dfm.dropna(subset=["anno", "mese"]).sort_values(["anno", "mese"])

    # Anno di riferimento: il più recente presente nei dati
    anni_disponibili = sorted(dfm["anno"].dropna().unique().tolist(), reverse=True)
    if not anni_disponibili:
        st.warning("⚠️ Nessun anno valido nei dati mensili.")
        return

    anno_sel = st.selectbox(
        "Anno di riferimento",
        anni_disponibili,
        index=0,
        format_func=lambda a: str(int(a)),
    )
    anno_sel = int(anno_sel)

    df_anno = dfm[dfm["anno"] == anno_sel].copy()

    # ---------------- KPI (mese corrente, YTD, since inception) ----------
    ultimo = df_anno.sort_values("mese").iloc[-1] if not df_anno.empty else None

    rend_mese = float(ultimo["rendimento_mensile_pct"]) if ultimo is not None else 0.0
    rend_ytd = float(ultimo["rendimento_cumulato_ytd_pct"]) if ultimo is not None else 0.0
    mese_label = (
        f"{MESI_IT_FULL[int(ultimo['mese'])]} {anno_sel}"
        if ultimo is not None else f"{anno_sel}"
    )

    # Since inception dalla vista cumulata
    df_cum_raw = _carica_rendimento_cumulato()
    rend_inception = 0.0
    inception_label = ""
    if df_cum_raw:
        dfc = pd.DataFrame(df_cum_raw)
        dfc["rendimento_cumulato_totale_pct"] = pd.to_numeric(
            dfc["rendimento_cumulato_totale_pct"], errors="coerce"
        )
        dfc = dfc.dropna(subset=["rendimento_cumulato_totale_pct"]).sort_values("periodo")
        if not dfc.empty:
            rend_inception = float(dfc.iloc[-1]["rendimento_cumulato_totale_pct"])
    # Data di inizio = prima operazione nota dai dati mensili
    primo_periodo = dfm.sort_values(["anno", "mese"]).iloc[0]
    inception_label = (
        f"dal 01/{int(primo_periodo['mese']):02d}/{int(primo_periodo['anno'])}"
    )

    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric(f"📆 {mese_label}", f"{rend_mese:+.2f}%")
    with k2:
        st.metric(f"🗓️ Dall'inizio dell'anno {anno_sel}", f"{rend_ytd:+.2f}%")
    with k3:
        st.metric(f"🚀 Sin dalla nascita {inception_label}", f"{rend_inception:+.2f}%")

    st.divider()

    # ---------------- Grafico principale Performance ---------------------
    df_graf = df_anno[["mese", "rendimento_mensile_pct",
                       "rendimento_cumulato_ytd_pct"]].copy()
    st.plotly_chart(
        _grafico_performance(df_graf, anno_sel),
        use_container_width=True,
    )

    st.divider()

    # ---------------- Grafici aggiuntivi ---------------------------------
    col1, col2 = st.columns(2)

    # 1) Rendimento anno per anno
    with col1:
        st.subheader("📊 Rendimento anno per anno")
        dati_annuali = _carica_rendimento_annuo()
        if dati_annuali:
            dfa = pd.DataFrame(dati_annuali)
            dfa.columns = [str(c).strip().lower() for c in dfa.columns]
            if "anno" in dfa.columns and "rendimento_annuo_pct" in dfa.columns:
                dfa["anno"] = pd.to_numeric(dfa["anno"], errors="coerce")
                dfa["rendimento_annuo_pct"] = pd.to_numeric(
                    dfa["rendimento_annuo_pct"], errors="coerce"
                )
                dfa = dfa.dropna(subset=["anno"]).sort_values("anno")
                colori = [
                    "#1f77b4" if v >= 0 else "#c0392b"
                    for v in dfa["rendimento_annuo_pct"].fillna(0)
                ]
                fig = go.Figure(go.Bar(
                    x=dfa["anno"].astype(int).astype(str),
                    y=dfa["rendimento_annuo_pct"],
                    marker=dict(color=colori),
                    text=[f"{v:.2f}%" for v in dfa["rendimento_annuo_pct"].fillna(0)],
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>%{y:.2f}%<extra></extra>",
                ))
                fig.add_hline(y=0, line_color="#888", line_width=1)
                fig.update_layout(
                    height=360, template="plotly_white",
                    yaxis=dict(ticksuffix="%"), showlegend=False,
                    margin=dict(t=20, b=30, l=40, r=20),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Dati annuali non disponibili nel formato atteso.")
        else:
            st.info("Nessun dato annuale disponibile.")

    # 2) Valore del portafoglio nel tempo (NAV di fine mese)
    with col2:
        st.subheader("💶 Valore portafoglio (fine mese)")
        dfm_graf = dfm.copy()
        dfm_graf["periodo"] = dfm_graf["anno"].astype(int).astype(str) + "-" + \
            dfm_graf["mese"].astype(int).map(lambda m: f"{m:02d}")
        fig = go.Figure(go.Scatter(
            x=dfm_graf["periodo"],
            y=dfm_graf["valore_fine_mese_eur"],
            mode="lines",
            fill="tozeroy",
            line=dict(color="#1f77b4", width=2),
            hovertemplate="<b>%{x}</b><br>€ %{y:,.0f}<extra></extra>",
        ))
        fig.update_layout(
            height=360, template="plotly_white",
            yaxis=dict(tickprefix="€ "), showlegend=False,
            margin=dict(t=20, b=30, l=60, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ---------------- Tabella dettaglio mensile --------------------------
    st.subheader(f"📋 Dettaglio mensile {anno_sel}")
    tab = df_anno.sort_values("mese").copy()
    tab_display = pd.DataFrame({
        "Mese": tab["mese"].map(lambda m: MESI_IT_FULL[int(m)].capitalize()),
        "Valore fine mese": tab["valore_fine_mese_eur"].map(lambda v: f"€ {v:,.2f}"),
        "Versato nel mese": tab["flusso_netto_eur"].map(lambda v: f"€ {v:,.2f}"),
        "Rend. mensile": tab["rendimento_mensile_pct"].map(lambda v: f"{v:+.2f}%"),
        "Cumulato YTD": tab["rendimento_cumulato_ytd_pct"].map(lambda v: f"{v:+.2f}%"),
    })
    st.dataframe(tab_display, use_container_width=True, hide_index=True)

    with st.expander("ℹ️ Come vengono calcolate le metriche"):
        st.markdown("""
        **Metodo time-weighted (TWR).** Il rendimento di ogni mese neutralizza
        l'effetto dei versamenti (PAC), così da misurare la performance reale del
        portafoglio e non la semplice crescita per nuovi apporti:

        `r_mese = (NAV_fine − NAV_inizio − versamenti) / (NAV_inizio + versamenti)`

        - **Rendimento mensile** (barre): performance del singolo mese.
        - **Cumulato YTD** (linea): prodotto composto dei rendimenti mensili da
          gennaio dell'anno selezionato — `Π(1 + rᵢ) − 1`.
        - **Sin dalla nascita**: rendimento cumulato composto dalla prima
          operazione (vista `v_portafoglio_rendimento_cumulato`).

        Il NAV di fine mese valorizza le quote cumulate detenute al prezzo di
        chiusura di fine mese (vista `v_portafoglio_rendimento_mensile`, basata
        su `etf_price_history`). I mesi senza prezzo storico disponibile non
        compaiono nel grafico.
        """)

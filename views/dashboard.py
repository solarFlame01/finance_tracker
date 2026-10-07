from views.bond_tracker import render_bond_tracker
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

def _carica_overview():
    dati = st.session_state.get("portfolio_overview")
    if dati:
        return dati
    try:
        from database import get_portfolio_overview
        dati = get_portfolio_overview()
        st.session_state.portfolio_overview = dati
        return dati
    except Exception:
        return []


def _carica_bond_summary():
    dati = st.session_state.get("bond_summary")
    if dati:
        return dati
    try:
        from database import get_bond_summary
        dati = get_bond_summary()
        st.session_state.bond_summary = dati
        return dati
    except Exception:
        return []


def render_riepilogo_portafoglio():
    """Riepilogo complessivo del portafoglio (ETF + Obbligazioni) con dettaglio
    affiancato per asset class."""
    overview = _carica_overview()
    bond = _carica_bond_summary()

    # --- Totali complessivi -------------------------------------------------
    tot_investito = sum(float(r.get("investito_eur") or 0) for r in overview)
    tot_valore = sum(float(r.get("valore_attuale_eur") or 0) for r in overview)
    tot_guadagno = tot_valore - tot_investito
    tot_rend = (tot_guadagno / tot_investito * 100) if tot_investito > 0 else 0.0

    etf_row = next((r for r in overview if r.get("asset_class") == "ETF"), {})
    bond_row = next((r for r in overview if r.get("asset_class") == "Obbligazioni"), {})

    st.markdown("<div class='section-title'>🌐 Portafoglio Complessivo</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="medium")
    with c1:
        st.metric("💰 Valore Totale", f"€ {tot_valore:,.2f}",
                  delta=f"€ {tot_guadagno:,.2f}" if tot_guadagno else None,
                  delta_color="normal" if tot_guadagno >= 0 else "inverse")
    with c2:
        st.metric("💵 Totale Investito", f"€ {tot_investito:,.2f}")
    with c3:
        color = "🟢" if tot_guadagno >= 0 else "🔴"
        st.metric(f"{color} Guadagno/Perdita", f"€ {tot_guadagno:,.2f}")
    with c4:
        st.metric("📊 Rendimento %", f"{tot_rend:.2f}%")

    st.caption("ℹ️ Le obbligazioni sono valorizzate al costo di acquisto "
               "(nessun prezzo di mercato disponibile).")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    # --- Dettaglio affiancato ETF | Obbligazioni ---------------------------
    col_etf, col_bond = st.columns(2, gap="large")

    with col_etf:
        st.markdown("<div class='subsection-title'>📈 ETF</div>", unsafe_allow_html=True)
        etf_inv = float(etf_row.get("investito_eur") or 0)
        etf_val = float(etf_row.get("valore_attuale_eur") or 0)
        etf_gain = float(etf_row.get("guadagno_eur") or 0)
        etf_rend = etf_row.get("rendimento_pct")
        e1, e2 = st.columns(2)
        with e1:
            st.metric("Valore di Mercato", f"€ {etf_val:,.2f}",
                      delta=f"€ {etf_gain:,.2f}" if etf_gain else None,
                      delta_color="normal" if etf_gain >= 0 else "inverse")
            st.metric("Investito", f"€ {etf_inv:,.2f}")
        with e2:
            st.metric("Rendimento", f"{float(etf_rend):.2f}%" if etf_rend is not None else "n/d")
            n_etf = len([r for r in (st.session_state.get('kpi_etf') or [])])
            st.metric("Posizioni", f"{n_etf}")

    with col_bond:
        st.markdown("<div class='subsection-title'>🏦 Obbligazioni</div>", unsafe_allow_html=True)
        bond_inv = float(bond_row.get("investito_eur") or 0)
        n_bond = len(bond)
        cedola_attesa = sum(float(b.get("cedola_annua_attesa_eur") or 0) for b in bond)
        cedole_incassate = sum(float(b.get("cedole_incassate_eur") or 0) for b in bond)
        cedole_lorde = sum(float(b.get("cedole_lorde_eur") or 0) for b in bond)
        ritenute = sum(float(b.get("ritenute_eur") or 0) for b in bond)
        b1, b2 = st.columns(2)
        with b1:
            st.metric("Capitale Investito", f"€ {bond_inv:,.2f}")
            st.metric("Titoli", f"{n_bond}")
        with b2:
            st.metric("Cedole Incassate (nette)", f"€ {cedole_incassate:,.2f}",
                      help=f"Cedole realmente incassate (lordo € {cedole_lorde:,.2f} "
                           f"− ritenute € {ritenute:,.2f}). Fonte: tabella bond_coupons.")
            st.metric("Cedola Annua Attesa", f"€ {cedola_attesa:,.2f}",
                      help="Stima su BTP a tasso fisso (nominale × tasso).")

        if bond:
            df_b = pd.DataFrame(bond)
            cols_show = [c for c in [
                "descrizione", "capitale_investito_eur", "tasso_cedolare_pct",
                "cedola_annua_attesa_eur", "cedole_incassate_eur",
                "n_cedole_incassate",
            ] if c in df_b.columns]
            st.dataframe(
                df_b[cols_show],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "descrizione": st.column_config.TextColumn("Titolo"),
                    "capitale_investito_eur": st.column_config.NumberColumn("Investito €", format="€ %.2f"),
                    "tasso_cedolare_pct": st.column_config.NumberColumn("Cedola %", format="%.2f%%"),
                    "cedola_annua_attesa_eur": st.column_config.NumberColumn("Cedola/anno €", format="€ %.2f"),
                    "cedole_incassate_eur": st.column_config.NumberColumn("Incassate € (nette)", format="€ %.2f"),
                    "n_cedole_incassate": st.column_config.NumberColumn("N° cedole", format="%d"),
                },
            )


# Sezione Dashboard
def render_dashboard():
    apply_dashboard_styling()
    
    st.markdown("<h1 style='text-align: center; margin-bottom: 30px;'>📊 Dashboard Portafoglio ETF</h1>", unsafe_allow_html=True)
    st.markdown("""
    <style>
            .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
                font-size: 17px;
            }
        </style>
    """, unsafe_allow_html=True)

    if st.session_state.etf_transactions:
        # Tab per organizzare le sezioni
        tab1, tab2, tab5,tab8, tab7, tab9, tab6, tab4  = st.tabs(["📈 Riepilogo", "📊 Analisi","🎯 Metriche","🏦 Bond Tracker", "🏆 Rendimento annuo", "💼 Prossimo PAC","➕ Inserisci Transazione", "⚙️ Impostazioni" ])
        
        # ===== TAB 1: RIEPILOGO =====
        with tab1:
            if st.button("🔄 Aggiorna Prezzi", use_container_width=True):
                from finance_info import aggiorna_prezzi_eft
                aggiorna_prezzi_eft()

            render_riepilogo_portafoglio()

            st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

            # DataFrame transazioni (usato piu' sotto per prezzo medio e posizioni)
            df_transaction = pd.DataFrame(st.session_state.etf_transactions)
            
            # ===== Tabella prezzo medio di acquisto =====
            st.markdown("<div class='section-title'>📍 Prezzo Medio di Acquisto</div>", unsafe_allow_html=True)
            df_prezzo_medio_acquisto = pd.DataFrame(st.session_state.prezzo_medio_acquisto)
            df_prezzo_medio_acquisto["diff_prezzo"] = (
                df_prezzo_medio_acquisto["price"]
                - df_prezzo_medio_acquisto["prezzo_medio_acquisto"]
            ).round(2)
            # Applica colori alla colonna Crescita %
            def color_crescita(val):
                if isinstance(val, (int, float)):
                    if val > 0:
                        return 'background-color: #90EE90'
                    elif val < 0:
                        return 'background-color: #FFB6C6'
                return ''
            
            if 'diff_prezzo' in df_prezzo_medio_acquisto.columns:
                df_prezzo_medio_acquisto_styled = (
                    df_prezzo_medio_acquisto.style
                    .map(color_crescita, subset=['diff_prezzo'])
                    .format({
                        'diff_prezzo': '{:.2f}',
                        'costo_investito_eur': '{:.2f}',
                        'prezzo_medio_acquisto': '{:.2f}',
                        'price': '{:.2f}'
                    })
                )
            st.dataframe(df_prezzo_medio_acquisto_styled, width="stretch", height=400, 
                         column_order=["ticker", "quantita", "costo_investito_eur", "prezzo_medio_acquisto", "price", "diff_prezzo", "ultima_operazione"],
            column_config={
                "ticker": st.column_config.TextColumn("Ticker"),
                "quantita": st.column_config.NumberColumn("Quantità", format="%.0f"),
                "costo_investito_eur": st.column_config.NumberColumn("Costo Investito €"),
                "prezzo_medio_acquisto": st.column_config.NumberColumn("Prezzo Medio Acquisto €"),
                "price": st.column_config.NumberColumn("Prezzo Corrente €"),
                "diff_prezzo": st.column_config.NumberColumn("Differenza Prezzo €"),
                "ultima_operazione": st.column_config.TextColumn("Ultima Operazione")
            })
            
            # Tabella principale con stile
            st.markdown("<div class='section-title'>📍 Posizioni Attuali</div>", unsafe_allow_html=True)
            df_transaction_display = df_transaction.drop(
                columns=[col for col in ["id", "created_at", "updated_at"] if col in df_transaction.columns], 
                errors='ignore'
            )
            
            
            if 'Crescita %' in df_transaction_display.columns:
                styled_df = (
                    df_transaction_display.style
                    .map(color_crescita, subset=['Crescita %'])
                    .format({
                        'Crescita %': '{:.2f}',
                        'Prezzo di acquisto': '{:.2f}',
                        'Prezzo corrente': '{:.2f}',
                        'Costo': '{:.2f}',
                        'Market Value': '{:.2f}',
                        'Quantità': '{:.0f}'
                    })
                )

                st.dataframe(styled_df, width="stretch", height=400)
            else:
                st.dataframe(df_transaction_display, width="stretch", height=400)

        
        # ===== TAB 2: ANALISI =====
        with tab2:
            st.markdown("<div class='section-title'>🎯 Analisi Portfolio</div>", unsafe_allow_html=True)
            st.markdown("<p style='color: #666; margin-bottom: 20px;'>Distribuzione degli investimenti per diverse dimensioni</p>", unsafe_allow_html=True)
            
            
            # ETF con migliore e peggiore performance
            col1, col2 = st.columns(2, gap="large")
            
            with col1:
                with st.expander("🏆 Top 3 ETF (Migliori Performance)", expanded=True):
                    df_top_3_etf = pd.DataFrame(st.session_state.top_3_etf)
                    if not df_top_3_etf.empty:
                        st.dataframe(df_top_3_etf, width="stretch")
                    else:
                        st.info("Nessun dato disponibile")
            
            with col2:
                with st.expander("📉 Bottom 3 ETF (Peggiori Performance)", expanded=True):
                    df_bottom_3_etf = pd.DataFrame(st.session_state.bottom_3_etf)
                    if not df_bottom_3_etf.empty:
                        st.dataframe(df_bottom_3_etf, width="stretch")
                    else:
                        st.info("Nessun dato disponibile")
                        
            st.markdown("<div class='subsection-title'>Distribuzione completa del portafoglio</div>", unsafe_allow_html=True)
            if st.session_state.asset_allocation:
                df_asset_allocation = pd.DataFrame(st.session_state.asset_allocation)
                if not df_asset_allocation.empty:
                    fig1 = go.Figure(data=[go.Pie(
                        labels=df_asset_allocation['asset_class'],           
                        values=df_asset_allocation['percentage'],
                        textinfo='label+percent',  # cosa mostrare
                        textposition='auto',     # fuori dalla fetta
                        textfont=dict(size=12),     # grandezza testo
                        hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>"
                    )])
                    fig1.update_layout(
                        title="",
                        height=400,
                        showlegend=True,
                        margin=dict(t=10, b=10)
                    )
                    st.plotly_chart(fig1, width="stretch")             
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
                            textinfo='label+percent',  # cosa mostrare
                            textposition='auto',     # fuori dalla fetta
                            textfont=dict(size=12),     # grandezza testo
                            hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>"
                        )])
                        fig1.update_layout(
                            title="",
                            height=400,
                            showlegend=True,
                            margin=dict(t=10, b=10)
                        )
                        st.plotly_chart(fig1, width="stretch")
            
            with col2:
                st.markdown("<div class='subsection-title'>Settore</div>", unsafe_allow_html=True)
                if st.session_state.distribuzione_settore:
                    df_dist_settore = pd.DataFrame(st.session_state.distribuzione_settore)
                    if not df_dist_settore.empty:
                        fig2 = go.Figure(data=[go.Pie(
                        labels=df_dist_settore['settore'],
                        values=df_dist_settore['distribuzione_pct'],
                        textinfo='label+percent',  # cosa mostrare
                        textposition='auto',     # fuori dalla fetta
                        textfont=dict(size=12),     # grandezza testo
                        hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>"
                    )])

                        fig2.update_layout(
                            title="",
                            height=400,
                            showlegend=True,
                            margin=dict(t=10, b=10)
                        )
                        st.plotly_chart(fig2, width="stretch")
            
            col3, col4 = st.columns(2, gap="large")
            
            with col3:
                st.markdown("<div class='subsection-title'>Valuta di Mercato</div>", unsafe_allow_html=True)
                if st.session_state.distribuzione_valuta_mercato:
                    df_dist_valuta = pd.DataFrame(st.session_state.distribuzione_valuta_mercato)
                    if not df_dist_valuta.empty:
                        fig3 = go.Figure(data=[go.Pie(
                            labels=df_dist_valuta['valuta_mercato'],
                            values=df_dist_valuta['distribuzione_pct'],
                            textinfo='label+percent',  # cosa mostrare
                            textposition='auto',     # fuori dalla fetta
                            textfont=dict(size=12),     # grandezza testo
                            hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>"
                        )])
                        fig3.update_layout(
                            title="",
                            height=400,
                            showlegend=True,
                            margin=dict(t=10, b=10)
                        )
                        st.plotly_chart(fig3, width="stretch")
            
            with col4:
                st.markdown("<div class='subsection-title'>Area Geografica</div>", unsafe_allow_html=True)
                if st.session_state.distribuzione_area_geografica:
                    df_dist_area = pd.DataFrame(st.session_state.distribuzione_area_geografica)
                    if not df_dist_area.empty:
                        fig4 = go.Figure(data=[go.Pie(
                            labels=df_dist_area['area_geografica'],
                            values=df_dist_area['distribuzione_pct'],
                            textinfo='label+percent',  # cosa mostrare
                            textposition='auto',     # fuori dalla fetta
                            textfont=dict(size=12),     # grandezza testo
                            hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>"
                        )])
                        fig4.update_layout(
                            title="",
                            height=400,
                            showlegend=True,
                            margin=dict(t=10, b=10)
                        )
                        st.plotly_chart(fig4, width="stretch")
            
            # Grafico a barre: Confronto Costo vs Market Value
            st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
            st.markdown("<div class='section-title'>📊 Confronto Costo vs Market Value per ETF</div>", unsafe_allow_html=True)
            
            if st.session_state.kpi_etf:
                df_kpi_chart = pd.DataFrame(st.session_state.kpi_etf)
                if not df_kpi_chart.empty and 'ticker' in df_kpi_chart.columns and 'costo_investito_eur' in df_kpi_chart.columns and 'market_value_attuale' in df_kpi_chart.columns:
                    df_chart_bars = df_kpi_chart[['ticker', 'costo_investito_eur', 'market_value_attuale']].copy()
                    df_chart_bars = (
                        df_chart_bars
                        .set_index("ticker")
                        .filter(regex=r"^(?!M\.).*", axis=0)
                        .reset_index()
                    )
                    
                    fig_bars = go.Figure(
                        data=[
                            go.Bar(x=df_chart_bars['ticker'], y=df_chart_bars['costo_investito_eur'], 
                                name='Costo Investito (EUR)', marker_color='red'),
                            go.Bar(x=df_chart_bars['ticker'], y=df_chart_bars['market_value_attuale'], 
                                name='Market Value Attuale', marker_color='green')
                        ]
                    )
                    fig_bars.update_layout(barmode='group', height=400)
                    st.plotly_chart(fig_bars, width="stretch")
        
        # ===== TAB 4: IMPOSTAZIONI =====
        with tab4:
            from views.impostazioni import render_impostazioni
            render_impostazioni()
        # ==== TAB METRICHE ====
        with tab5:
            from views.metriche import render_metriche
            render_metriche()
        # ==== TAB INSERISCI TRANSAZIONE ====
        with tab6:
            from views.gestione_eft import render_gestione_etf
            render_gestione_etf()
        # ==== TAB RENDIMENTO ANNUO ====
        with tab7:
            from views.rendimento_annuo import render_rendimento_annuo
            render_rendimento_annuo()
        # ==== TAB PROSSIMO PAC ====
        with tab9:
            from views.prossimo_pac import render_prossimo_pac
            render_prossimo_pac()
        # ==== TAB BOND TRACKER ====
        with tab8:
            render_bond_tracker()
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime


# ============================================================
# Helper: dati di partenza derivati dal portafoglio
# ============================================================
def _stima_parametri_portafoglio():
    """
    Deriva dai dati in sessione i valori di default per le proiezioni.

    Perimetro: tutti i default sono calcolati sul SOLO comparto ETF
    (la vista `etf_transaction_updated` da cui provengono le transazioni
    esclude i bond 'M.%'), per coerenza tra capitale iniziale e versamenti.

    Ritorna:
      - valore_attuale: market value corrente degli ETF (somma Market Value)
      - valore_attuale_totale: market value ETF + Bond (solo informativo)
      - versamento_medio_mensile: capitale investito in ETF / mesi coperti
      - versamento_mediano_acquisto: importo mediano per mese con acquisti
        (meno sensibile ai mesi senza versamenti e agli outlier)
      - cagr: rendimento annuo composto storico (se disponibile)
      - mesi_storici: numero di mesi di calendario coperti dalla media
      - mesi_con_acquisti: numero di mesi in cui c'e' stato almeno un acquisto
      - n_operazioni: numero di righe transazione considerate

    Tutti i valori sono robusti ai dati mancanti: se non calcolabili
    ritornano None e la UI usera' un fallback sensato.
    """
    out = {
        'valore_attuale': None,
        'valore_attuale_totale': None,
        'versamento_medio_mensile': None,
        'versamento_mediano_acquisto': None,
        'capitale_investito': None,
        'mesi_storici': None,
        'mesi_con_acquisti': None,
        'n_operazioni': None,
        'cagr': None,
    }

    df_tx = pd.DataFrame(st.session_state.get('etf_transactions', []))

    # --- Valore attuale ETF (perimetro coerente coi versamenti) ---------
    if not df_tx.empty and 'Market Value' in df_tx.columns:
        out['valore_attuale'] = float(pd.to_numeric(df_tx['Market Value'], errors='coerce').sum())

    # --- Valore totale ETF + Bond (solo informativo) --------------------
    overview = st.session_state.get('portfolio_overview', [])
    if overview:
        df_ov = pd.DataFrame(overview)
        if not df_ov.empty and 'valore_attuale_eur' in df_ov.columns:
            out['valore_attuale_totale'] = float(
                pd.to_numeric(df_ov['valore_attuale_eur'], errors='coerce').sum()
            )
    # Fallback: se non ho il valore ETF, uso il totale
    if (out['valore_attuale'] is None or out['valore_attuale'] == 0) and out['valore_attuale_totale']:
        out['valore_attuale'] = out['valore_attuale_totale']

    # --- Versamenti storici (acquisti ETF) ------------------------------
    # NB: la vista espone "Costo" = abs(importo_euro), sempre positivo, e NON
    # espone il tipo operazione. Sugli ETF lo storico e' composto da acquisti,
    # ma eventuali vendite future NON sarebbero distinguibili qui: verrebbero
    # sommate come versamenti. Limite dichiarato anche nella UI.
    if not df_tx.empty and {'Data acquisto', 'Costo'}.issubset(df_tx.columns):
        tmp = df_tx.copy()
        tmp['Data acquisto'] = pd.to_datetime(tmp['Data acquisto'], errors='coerce')
        tmp['Costo'] = pd.to_numeric(tmp['Costo'], errors='coerce')
        tmp = tmp.dropna(subset=['Data acquisto', 'Costo'])
        tmp = tmp[tmp['Costo'] > 0]
        if not tmp.empty:
            capitale_investito = float(tmp['Costo'].sum())
            data_inizio = tmp['Data acquisto'].min()
            data_fine = tmp['Data acquisto'].max()

            # Mesi di calendario coperti (robusto, indipendente da 30.44)
            mesi_storici = (data_fine.year - data_inizio.year) * 12 \
                + (data_fine.month - data_inizio.month) + 1
            mesi_storici = max(1, int(mesi_storici))

            # Raggruppa per mese-calendario per avere statistiche robuste
            per_mese = tmp.groupby(tmp['Data acquisto'].dt.to_period('M'))['Costo'].sum()
            mesi_con_acquisti = int(per_mese.shape[0])

            out['capitale_investito'] = capitale_investito
            out['mesi_storici'] = mesi_storici
            out['mesi_con_acquisti'] = mesi_con_acquisti
            out['n_operazioni'] = int(tmp.shape[0])
            # Media spalmata su tutti i mesi del calendario
            out['versamento_medio_mensile'] = capitale_investito / mesi_storici
            # Mediana degli importi nei soli mesi con acquisti (PAC tipico)
            out['versamento_mediano_acquisto'] = float(per_mese.median())

    # --- CAGR storico ---------------------------------------------------
    try:
        from finance_info import calculate_CAGR
        out['cagr'] = calculate_CAGR()
    except Exception:
        out['cagr'] = None

    return out


# ============================================================
# Motore di proiezione deterministico
# ============================================================
def _proietta_deterministico(valore_iniziale, versamento_mensile, anni,
                             rendimento_annuo_pct, step_up_annuo_pct):
    """
    Proietta mese per mese l'evoluzione del capitale con interesse composto
    e versamenti periodici (PAC), opzionalmente crescenti ogni anno (step-up).

    Il rendimento annuo viene convertito in rendimento mensile equivalente
    (composto): (1 + r_annuo)^(1/12) - 1.

    Ritorna un DataFrame mensile con capitale, capitale versato cumulato
    e guadagno.
    """
    r_mensile = (1 + rendimento_annuo_pct / 100.0) ** (1 / 12) - 1
    mesi = int(round(anni * 12))

    capitale = float(valore_iniziale)
    versato_cumulato = float(valore_iniziale)
    versamento_corrente = float(versamento_mensile)

    righe = []
    oggi = datetime.now()
    for m in range(1, mesi + 1):
        # Step-up: aumenta il versamento all'inizio di ogni nuovo anno
        if step_up_annuo_pct and m > 1 and (m - 1) % 12 == 0:
            versamento_corrente *= (1 + step_up_annuo_pct / 100.0)

        # Rendimento sul capitale esistente + nuovo versamento a inizio mese
        capitale = capitale * (1 + r_mensile) + versamento_corrente
        versato_cumulato += versamento_corrente

        data = oggi + pd.DateOffset(months=m)
        righe.append({
            'mese': m,
            'data': data,
            'capitale': capitale,
            'versato_cumulato': versato_cumulato,
            'guadagno': capitale - versato_cumulato,
            'versamento_mese': versamento_corrente,
        })

    return pd.DataFrame(righe)


# ============================================================
# Simulazione Monte Carlo (incertezza sul rendimento)
# ============================================================
def _proietta_montecarlo(valore_iniziale, versamento_mensile, anni,
                         rendimento_annuo_pct, volatilita_annua_pct,
                         step_up_annuo_pct, n_simulazioni=1000, seed=42):
    """
    Simula n percorsi del portafoglio estraendo rendimenti mensili da una
    distribuzione normale con media e deviazione standard mensili coerenti
    con i parametri annui forniti.

    Ritorna i percentili (5, 25, 50, 75, 95) del capitale finale per ogni
    mese e la distribuzione dei valori finali.
    """
    rng = np.random.default_rng(seed)
    mesi = int(round(anni * 12))

    mu_mensile = (1 + rendimento_annuo_pct / 100.0) ** (1 / 12) - 1
    sigma_mensile = (volatilita_annua_pct / 100.0) / np.sqrt(12)

    # Matrice rendimenti: (n_simulazioni x mesi)
    rendimenti = rng.normal(mu_mensile, sigma_mensile, size=(n_simulazioni, mesi))

    capitali = np.full(n_simulazioni, float(valore_iniziale))
    versamento_corrente = float(versamento_mensile)

    traiettorie = np.zeros((n_simulazioni, mesi))
    for m in range(mesi):
        if step_up_annuo_pct and m > 0 and m % 12 == 0:
            versamento_corrente *= (1 + step_up_annuo_pct / 100.0)
        capitali = capitali * (1 + rendimenti[:, m]) + versamento_corrente
        traiettorie[:, m] = capitali

    percentili = {
        'p5': np.percentile(traiettorie, 5, axis=0),
        'p25': np.percentile(traiettorie, 25, axis=0),
        'p50': np.percentile(traiettorie, 50, axis=0),
        'p75': np.percentile(traiettorie, 75, axis=0),
        'p95': np.percentile(traiettorie, 95, axis=0),
    }
    return percentili, traiettorie[:, -1]


# ============================================================
# Risolutore obiettivo: versamento mensile necessario
# ============================================================
def _versamento_per_obiettivo(valore_iniziale, obiettivo, anni, rendimento_annuo_pct):
    """
    Calcola il versamento mensile costante necessario per raggiungere
    `obiettivo` in `anni` dato un rendimento annuo atteso.

    Usa la formula del valore futuro di un capitale piu' una rendita con
    versamenti a fine periodo, coerente col motore `_proietta_deterministico`
    (rendimento sul capitale esistente, poi aggiunta del versamento):
        FV = VI*(1+i)^n + PMT * [((1+i)^n - 1)/i]
    da cui si ricava PMT. Con i ~ 0 degenera nel caso lineare.
    """
    i = (1 + rendimento_annuo_pct / 100.0) ** (1 / 12) - 1
    n = int(round(anni * 12))
    if n <= 0:
        return None

    fv_iniziale = valore_iniziale * (1 + i) ** n
    residuo = obiettivo - fv_iniziale

    if residuo <= 0:
        return 0.0  # L'obiettivo e' gia' raggiungibile senza versare nulla

    if abs(i) < 1e-9:
        pmt = residuo / n
    else:
        fattore = ((1 + i) ** n - 1) / i
        pmt = residuo / fattore
    return pmt


def _rendimento_per_obiettivo(valore_iniziale, versamento_mensile, obiettivo, anni):
    """
    Trova, per bisezione, il rendimento annuo necessario a raggiungere
    l'obiettivo dati valore iniziale, versamento mensile e orizzonte.
    Ritorna None se non raggiungibile entro un rendimento del 50% annuo.
    """
    def fv(rendimento_pct):
        df = _proietta_deterministico(valore_iniziale, versamento_mensile, anni, rendimento_pct, 0)
        return df['capitale'].iloc[-1] if not df.empty else valore_iniziale

    lo, hi = -50.0, 50.0
    if fv(hi) < obiettivo:
        return None
    if fv(lo) > obiettivo:
        return lo
    for _ in range(80):
        mid = (lo + hi) / 2
        if fv(mid) < obiettivo:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ============================================================
# View principale
# ============================================================
def render_proiezioni_future():
    st.header("🔮 Proiezioni Future")
    st.markdown(
        "Proietta la crescita del portafoglio considerando i tuoi versamenti medi. "
        "Modifica i parametri per capire **quale strategia adottare** per raggiungere "
        "un obiettivo rispetto a un altro."
    )

    stime = _stima_parametri_portafoglio()

    # Fallback sensati se i dati non sono disponibili.
    # Capitale iniziale: patrimonio investito che continua a rendere ->
    # include anche i bond (ETF + Bond). I VERSAMENTI invece sono solo il
    # PAC ETF, perche' i bond l'utente li compra spot (non ricorrenti).
    valore_etf = stime['valore_attuale'] if stime['valore_attuale'] else 0.0
    valore_totale = stime['valore_attuale_totale'] if stime['valore_attuale_totale'] else valore_etf
    capitale_iniziale_default = valore_totale if valore_totale else valore_etf
    media_spalmata = stime['versamento_medio_mensile']
    pac_tipico = stime['versamento_mediano_acquisto']
    cagr_default = stime['cagr'] if (stime['cagr'] is not None and stime['cagr'] > 0) else 6.0

    # --- Scelta di come stimare il versamento medio --------------------
    # Due definizioni legittime di "versamento medio"; lascio scegliere
    # all'utente ed espongo il metodo, invece di nasconderlo.
    # SOLO ETF: il PAC riguarda gli ETF, i bond sono acquisti spot.
    st.markdown("**Base di calcolo del versamento ricorrente** (solo PAC ETF)")
    opzioni_base = []
    if media_spalmata:
        opzioni_base.append(f"Media spalmata su tutti i mesi · €{media_spalmata:,.0f}/mese")
    if pac_tipico:
        opzioni_base.append(f"PAC tipico (mediana dei mesi con acquisti) · €{pac_tipico:,.0f}/mese")
    opzioni_base.append("Personalizzato")

    scelta_base = st.radio(
        "Come stimare il versamento mensile di partenza?",
        opzioni_base, index=0, horizontal=False,
        help=(
            "Media spalmata = capitale ETF investito / mesi totali di calendario "
            "(diluita dai mesi senza acquisti). "
            "PAC tipico = importo mediano nei soli mesi in cui hai comprato "
            "(piu' vicino al tuo versamento abituale)."
        )
    )

    if scelta_base.startswith("Media spalmata"):
        versamento_default = media_spalmata or 300.0
    elif scelta_base.startswith("PAC tipico"):
        versamento_default = pac_tipico or 300.0
    else:
        versamento_default = media_spalmata or pac_tipico or 300.0

    # Riepilogo dei dati storici usati come base
    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric(
                "Capitale iniziale (ETF+Bond)", f"€{capitale_iniziale_default:,.0f}",
                help=(
                    f"Patrimonio investito di partenza (continua a rendere). "
                    f"Di cui ETF: €{valore_etf:,.0f}"
                    + (f", Bond: €{valore_totale - valore_etf:,.0f}." if valore_totale > valore_etf else ".")
                )
            )
        with c2:
            st.metric(
                "di cui ETF (base PAC)", f"€{valore_etf:,.0f}",
                help="Market value del solo comparto ETF, su cui agisce il versamento ricorrente."
            )
        with c3:
            if media_spalmata:
                st.metric(
                    "Versamento mensile PAC ETF",
                    f"€{versamento_default:,.0f}",
                    help=(
                        f"Capitale ETF investito: €{stime['capitale_investito']:,.0f} "
                        f"su {stime['mesi_storici']} mesi di calendario "
                        f"({stime['mesi_con_acquisti']} con almeno un acquisto, "
                        f"{stime['n_operazioni']} operazioni totali)."
                    )
                )
            else:
                st.metric("Versamento mensile PAC ETF", "n/d")
        with c4:
            if stime['cagr'] is not None:
                st.metric("Rendimento storico (CAGR)", f"{stime['cagr']:.2f}%")
            else:
                st.metric("Rendimento storico (CAGR)", "n/d")

    st.info(
        "ℹ️ **Logica della proiezione** — Il **versamento ricorrente** è stimato dai "
        "soli **acquisti ETF** (il tuo PAC): i **bond**, che compri spot, non entrano "
        "nel versamento mensile ma sono inclusi nel **capitale iniziale** perché "
        "continuano a rendere. Lo storico ETF è composto da acquisti; eventuali vendite "
        "non sarebbero distinguibili e verrebbero contate come versamenti. Puoi "
        "correggere manualmente i valori qui sotto se non rispecchiano il tuo piano."
    )

    st.divider()

    # ---------------- Parametri configurabili ----------------
    st.subheader("⚙️ Parametri della proiezione")

    col1, col2, col3 = st.columns(3)
    with col1:
        valore_iniziale = st.number_input(
            "Capitale iniziale (€)",
            min_value=0.0, value=float(round(capitale_iniziale_default, 2)), step=500.0, format="%.2f",
            help="Patrimonio di partenza. Precompilato col valore attuale ETF + Bond "
                 "(entrambi continuano a rendere)."
        )
        versamento_mensile = st.number_input(
            "Versamento mensile PAC (€)",
            min_value=0.0, value=float(round(versamento_default, 2)), step=50.0, format="%.2f",
            help="Solo PAC ETF ricorrente. Precompilato con la media storica dei tuoi "
                 "acquisti ETF (i bond spot non sono inclusi)."
        )
    with col2:
        anni = st.slider("Orizzonte temporale (anni)", min_value=1, max_value=40, value=15, step=1)
        rendimento_annuo = st.slider(
            "Rendimento annuo atteso (%)",
            min_value=-5.0, max_value=15.0, value=float(round(cagr_default, 1)), step=0.5,
            help="Precompilato con il CAGR storico. Rendimento medio composto atteso."
        )
    with col3:
        step_up = st.slider(
            "Step-up annuale versamento (%)",
            min_value=0.0, max_value=20.0, value=0.0, step=0.5,
            help="Aumento percentuale del versamento ogni anno (es. per adeguarlo allo stipendio)."
        )
        inflazione = st.slider(
            "Inflazione attesa (%)",
            min_value=0.0, max_value=8.0, value=2.0, step=0.5,
            help="Usata per mostrare il potere d'acquisto reale del capitale futuro."
        )

    with st.expander("🎲 Parametri avanzati (scenario con incertezza)"):
        col_a, col_b = st.columns(2)
        with col_a:
            volatilita = st.slider(
                "Volatilità annua attesa (%)",
                min_value=0.0, max_value=40.0, value=15.0, step=1.0,
                help="Deviazione standard dei rendimenti. Più alta = scenari più dispersi. "
                     "S&P 500 ~15-20%, portafoglio bilanciato ~8-12%."
            )
            spread_scenari = st.slider(
                "Spread scenari ottimistico/pessimistico (±%)",
                min_value=1.0, max_value=8.0, value=3.0, step=0.5,
                help="Quanto si discostano gli scenari ottimistico e pessimistico dal rendimento atteso."
            )
        with col_b:
            n_sim = st.select_slider(
                "Numero di simulazioni Monte Carlo",
                options=[200, 500, 1000, 2000, 5000], value=1000,
                help="Più simulazioni = bande di confidenza più stabili (ma calcolo più lento)."
            )

    # ---------------- Calcolo proiezioni ----------------
    df_atteso = _proietta_deterministico(valore_iniziale, versamento_mensile, anni, rendimento_annuo, step_up)
    df_ott = _proietta_deterministico(valore_iniziale, versamento_mensile, anni, rendimento_annuo + spread_scenari, step_up)
    df_pess = _proietta_deterministico(valore_iniziale, versamento_mensile, anni, rendimento_annuo - spread_scenari, step_up)

    capitale_finale = df_atteso['capitale'].iloc[-1]
    versato_totale = df_atteso['versato_cumulato'].iloc[-1]
    guadagno_totale = capitale_finale - versato_totale
    # Valore reale (al netto dell'inflazione)
    capitale_reale = capitale_finale / ((1 + inflazione / 100.0) ** anni)

    # ---------------- Risultati sintetici ----------------
    st.divider()
    st.subheader(f"📊 Risultato atteso tra {anni} anni")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Capitale finale stimato", f"€{capitale_finale:,.0f}")
    with m2:
        st.metric("Totale versato", f"€{versato_totale:,.0f}")
    with m3:
        st.metric("Guadagno da rendimenti", f"€{guadagno_totale:,.0f}",
                  delta=f"{(guadagno_totale / versato_totale * 100) if versato_totale else 0:.1f}%")
    with m4:
        st.metric("Valore reale (netto inflazione)", f"€{capitale_reale:,.0f}",
                  help=f"Potere d'acquisto a prezzi di oggi con inflazione al {inflazione:.1f}%.")

    st.caption(
        f"Scenario ottimistico ({rendimento_annuo + spread_scenari:.1f}%): "
        f"**€{df_ott['capitale'].iloc[-1]:,.0f}**  |  "
        f"Scenario pessimistico ({rendimento_annuo - spread_scenari:.1f}%): "
        f"**€{df_pess['capitale'].iloc[-1]:,.0f}**"
    )

    # ---------------- Grafico scenari deterministici ----------------
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_ott['data'], y=df_ott['capitale'], name=f"Ottimistico ({rendimento_annuo + spread_scenari:.1f}%)",
        line=dict(color='rgba(44,160,44,0.4)', width=1)
    ))
    fig.add_trace(go.Scatter(
        x=df_pess['data'], y=df_pess['capitale'], name=f"Pessimistico ({rendimento_annuo - spread_scenari:.1f}%)",
        line=dict(color='rgba(214,39,40,0.4)', width=1), fill='tonexty', fillcolor='rgba(31,119,180,0.08)'
    ))
    fig.add_trace(go.Scatter(
        x=df_atteso['data'], y=df_atteso['capitale'], name=f"Atteso ({rendimento_annuo:.1f}%)",
        line=dict(color='#1f77b4', width=3)
    ))
    fig.add_trace(go.Scatter(
        x=df_atteso['data'], y=df_atteso['versato_cumulato'], name="Capitale versato",
        line=dict(color='#888', width=2, dash='dash')
    ))
    fig.update_layout(
        title="Evoluzione del capitale: scenari a confronto",
        xaxis_title="Anno", yaxis_title="Capitale (€)",
        height=450, hovermode='x unified', margin=dict(t=50, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)

    # ---------------- Monte Carlo ----------------
    st.divider()
    st.subheader("🎲 Analisi probabilistica (Monte Carlo)")
    st.caption(
        "Simula migliaia di percorsi di mercato con volatilità, per stimare un intervallo "
        "di esiti plausibili invece di un singolo numero."
    )

    percentili, finali = _proietta_montecarlo(
        valore_iniziale, versamento_mensile, anni, rendimento_annuo, volatilita, step_up, n_simulazioni=int(n_sim)
    )
    date_mc = df_atteso['data']

    fig_mc = go.Figure()
    fig_mc.add_trace(go.Scatter(x=date_mc, y=percentili['p95'], name="95° percentile",
                                line=dict(width=0), showlegend=False))
    fig_mc.add_trace(go.Scatter(x=date_mc, y=percentili['p5'], name="Intervallo 5°-95°",
                                line=dict(width=0), fill='tonexty', fillcolor='rgba(31,119,180,0.15)'))
    fig_mc.add_trace(go.Scatter(x=date_mc, y=percentili['p75'], name="75° percentile",
                                line=dict(width=0), showlegend=False))
    fig_mc.add_trace(go.Scatter(x=date_mc, y=percentili['p25'], name="Intervallo 25°-75°",
                                line=dict(width=0), fill='tonexty', fillcolor='rgba(31,119,180,0.3)'))
    fig_mc.add_trace(go.Scatter(x=date_mc, y=percentili['p50'], name="Mediana",
                                line=dict(color='#1f77b4', width=3)))
    fig_mc.update_layout(
        title=f"Distribuzione degli esiti ({int(n_sim)} simulazioni)",
        xaxis_title="Anno", yaxis_title="Capitale (€)",
        height=450, hovermode='x unified', margin=dict(t=50, b=10)
    )
    st.plotly_chart(fig_mc, use_container_width=True)

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.metric("Caso sfavorevole (5%)", f"€{np.percentile(finali, 5):,.0f}",
                  help="Solo il 5% degli scenari finisce sotto questo valore.")
    with mc2:
        st.metric("Caso mediano (50%)", f"€{np.percentile(finali, 50):,.0f}")
    with mc3:
        st.metric("Caso favorevole (95%)", f"€{np.percentile(finali, 95):,.0f}",
                  help="Solo il 5% degli scenari supera questo valore.")

    # ---------------- Pianificazione per obiettivo ----------------
    st.divider()
    st.subheader("🎯 Pianifica per un obiettivo")
    st.caption("Imposta un capitale da raggiungere: calcolo cosa serve per arrivarci.")

    col_o1, col_o2 = st.columns(2)
    with col_o1:
        obiettivo = st.number_input(
            "Obiettivo di capitale (€)",
            min_value=0.0, value=float(round(max(capitale_finale, 100000), -3)), step=5000.0, format="%.2f"
        )
    with col_o2:
        modalita = st.radio(
            "Cosa vuoi calcolare?",
            ["Versamento mensile necessario", "Rendimento annuo necessario"],
            help="Fissa l'orizzonte e scopri la leva su cui agire."
        )

    if modalita == "Versamento mensile necessario":
        pmt = _versamento_per_obiettivo(valore_iniziale, obiettivo, anni, rendimento_annuo)
        if pmt is None:
            st.error("Orizzonte temporale non valido.")
        elif pmt == 0.0:
            st.success(
                f"🎉 Con il solo capitale iniziale e un rendimento del {rendimento_annuo:.1f}% "
                f"raggiungi l'obiettivo senza versamenti aggiuntivi."
            )
        else:
            delta = pmt - versamento_mensile
            st.success(
                f"Per raggiungere **€{obiettivo:,.0f}** in **{anni} anni** "
                f"(rendimento {rendimento_annuo:.1f}%) devi versare **€{pmt:,.0f}/mese**."
            )
            if delta > 0:
                st.info(f"➕ Sono **€{delta:,.0f}/mese in più** rispetto al tuo versamento attuale (€{versamento_mensile:,.0f}).")
            else:
                st.info(f"✅ È **€{abs(delta):,.0f}/mese in meno** rispetto al tuo versamento attuale: hai margine.")
    else:
        r = _rendimento_per_obiettivo(valore_iniziale, versamento_mensile, obiettivo, anni)
        if r is None:
            st.error(
                "Obiettivo non raggiungibile con un rendimento ragionevole (<50%/anno) "
                "mantenendo questo versamento. Aumenta il versamento, l'orizzonte o riduci l'obiettivo."
            )
        else:
            st.success(
                f"Per raggiungere **€{obiettivo:,.0f}** in **{anni} anni** versando "
                f"**€{versamento_mensile:,.0f}/mese** serve un rendimento annuo del **{r:.2f}%**."
            )
            if r > rendimento_annuo + 2:
                st.warning(
                    f"⚠️ È {r - rendimento_annuo:.1f} punti sopra il tuo rendimento atteso ({rendimento_annuo:.1f}%): "
                    "obiettivo ambizioso, valuta più rischio o più versamenti."
                )
            elif r < rendimento_annuo:
                st.info("✅ È sotto il tuo rendimento atteso: obiettivo prudente e ben raggiungibile.")

    # ---------------- Dettaglio anno per anno ----------------
    with st.expander("📅 Dettaglio anno per anno (scenario atteso)"):
        df_annuale = df_atteso[df_atteso['mese'] % 12 == 0].copy()
        if df_annuale.empty or df_annuale['mese'].max() != df_atteso['mese'].max():
            df_annuale = pd.concat([df_annuale, df_atteso.tail(1)]).drop_duplicates(subset='mese')
        df_annuale['Anno'] = (df_annuale['mese'] / 12).round().astype(int)
        df_annuale_display = df_annuale[['Anno', 'capitale', 'versato_cumulato', 'guadagno']].copy()
        df_annuale_display.columns = ['Anno', 'Capitale (€)', 'Versato (€)', 'Guadagno (€)']
        st.dataframe(
            df_annuale_display,
            hide_index=True, use_container_width=True,
            column_config={
                'Capitale (€)': st.column_config.NumberColumn(format="%.0f"),
                'Versato (€)': st.column_config.NumberColumn(format="%.0f"),
                'Guadagno (€)': st.column_config.NumberColumn(format="%.0f"),
            }
        )

    st.caption(
        "⚠️ Le proiezioni sono stime basate su ipotesi di rendimento costante e non "
        "garantiscono risultati futuri. I rendimenti reali variano nel tempo."
    )

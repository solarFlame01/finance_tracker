# app.py
import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import plotly.graph_objects as go

# Configurazione pagina
st.set_page_config(
    page_title="ETF Portfolio Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"  # Nasconde la sidebar di default
)

# Percorsi file
DATA_FILE = "etf_data.json"
ETF_DETAILS_FILE = "etf_details.csv"

# Inizializzazione session state
if 'etf_data' not in st.session_state:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            st.session_state.etf_data = json.load(f)
    else:
        st.session_state.etf_data = []

if 'etf_details' not in st.session_state:
    if os.path.exists(ETF_DETAILS_FILE):
        st.session_state.etf_details = pd.read_csv(ETF_DETAILS_FILE)
    else:
        st.session_state.etf_details = pd.DataFrame()

# Intermediari predefiniti
INTERMEDIARI = ["Directa", "Fineco", "Degiro", "IBKR", "Altro"]

# Funzione per salvare i dati
def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(st.session_state.etf_data, f, indent=2)

# Funzione per calcolare le metriche
def calculate_metrics(transactions):
    if not transactions:
        return pd.DataFrame()
    
    df = pd.DataFrame(transactions)
    
    # Assicuriamoci che le colonne necessarie esistano
    required_cols = ['Quantità', 'Prezzo di acquisto', 'Prezzo corrente']
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0
    
    # Calcoli
    df['Costo'] = df['Quantità'] * df['Prezzo di acquisto']
    df['Market Value'] = df['Quantità'] * df['Prezzo corrente']
    df['Crescita %'] = ((df['Market Value'] - df['Costo']) / df['Costo'] * 100).round(2)
    
    # Formattazione
    if 'Data acquisto' in df.columns:
        df['Data acquisto'] = pd.to_datetime(df['Data acquisto'], errors='coerce').dt.strftime('%d/%m/%Y')
    
    numeric_cols = ['Prezzo di acquisto', 'Prezzo corrente', 'Costo', 'Market Value']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].round(2)
    
    return df

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

# Sezione Gestione ETF
def render_gestione_etf():
    st.header("📝 Gestione ETF")
    
    # Form per aggiunta/modifica
    with st.form("etf_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            ticker = st.text_input("Ticker*", max_chars=10, help="Codice identificativo dell'ETF (es: VWCE)")
            quantita = st.number_input("Quantità*", min_value=0.0, format="%.4f", help="Numero di quote acquistate")
            prezzo_acquisto = st.number_input("Prezzo di acquisto*", min_value=0.0, format="%.4f", help="Prezzo per quota al momento dell'acquisto")
            data_acquisto = st.date_input("Data di acquisto*", value=datetime.now())
            prezzo_corrente = st.number_input("Prezzo corrente*", min_value=0.0, format="%.4f", value=0.0, help="Prezzo corrente per quota")
            
        with col2:
            valuta = st.selectbox("Valuta*", ["EUR", "USD", "GBP", "CHF"], index=0)
            emittente = st.text_input("Emittente*", help="Nome della società che emette l'ETF (es: Vanguard)")
            tassa = st.number_input("Tassa (%)", min_value=0.0, max_value=100.0, value=0.0, format="%.2f", help="Commissioni di gestione annuali")
            intermediario = st.selectbox("Intermediario", INTERMEDIARI, index=0, help="Piattaforma di trading utilizzata")
            spese_acquisto = st.number_input("Spese di acquisto (€)", min_value=0.0, value=0.0, format="%.2f", help="Commissioni di acquisto")
            transazione_prova = st.checkbox("Transazione di prova", help="Segnala se è una transazione di test")
        
        # ISIN opzionale
        isin = st.text_input("ISIN (opzionale)", max_chars=12, help="Codice ISIN internazionale (es: IE00BK5BQT80)")
        
        col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
        with col_b2:
            submitted = st.form_submit_button("💾 Salva Transazione", type="primary", width='stretch')
        
        if submitted:
            if not all([ticker, quantita > 0, prezzo_acquisto > 0, prezzo_corrente >= 0, emittente]):
                st.error("❌ Compila tutti i campi obbligatori (*) con valori validi")
            else:
                nuova_transazione = {
                    "Ticker": ticker.upper(),
                    "Quantità": float(quantita),
                    "Prezzo di acquisto": float(prezzo_acquisto),
                    "Data acquisto": data_acquisto.strftime("%Y-%m-%d"),
                    "Prezzo corrente": float(prezzo_corrente),
                    "Valuta": valuta,
                    "Emittente": emittente,
                    "Tassa": float(tassa),
                    "Intermediario": intermediario,
                    "Spese acquisto": float(spese_acquisto),
                    "Transazione prova": transazione_prova,
                    "ISIN": isin.upper() if isin else "",
                    "Data inserimento": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                st.session_state.etf_data.append(nuova_transazione)
                save_data()
                st.success("✅ Transazione salvata con successo!")
    
    # Visualizza e gestisci transazioni esistenti
    st.subheader("📋 Transazioni Salvate")
    if st.session_state.etf_data:
        df_transazioni = pd.DataFrame(st.session_state.etf_data)
        
        # Mostra tabella riepilogativa
        if not df_transazioni.empty:
            # Seleziona le colonne da mostrare
            colonne_riepilogo = ['Ticker', 'Quantità', 'Prezzo di acquisto', 'Data acquisto', 'Emittente', 'Intermediario']
            colonne_disponibili = [col for col in colonne_riepilogo if col in df_transazioni.columns]
            
            if colonne_disponibili:
                df_display = df_transazioni[colonne_disponibili]
                st.dataframe(df_display, width='stretch', height=300)
            
            # Pulsante per eliminare transazioni
            st.subheader("🗑️ Gestione Transazioni")
            if len(st.session_state.etf_data) > 0:
                transazioni_per_eliminare = st.multiselect(
                    "Seleziona transazioni da eliminare:",
                    options=[f"{t['Ticker']} - {t['Data acquisto']} - {t['Quantità']} quote" 
                            for t in st.session_state.etf_data],
                    placeholder="Seleziona una o più transazioni"
                )
                
                if transazioni_per_eliminare and st.button("Elimina transazioni selezionate", type="secondary"):
                    # Trova gli indici delle transazioni da eliminare
                    indici_da_eliminare = []
                    for idx, trans in enumerate(st.session_state.etf_data):
                        descrizione = f"{trans['Ticker']} - {trans['Data acquisto']} - {trans['Quantità']} quote"
                        if descrizione in transazioni_per_eliminare:
                            indici_da_eliminare.append(idx)
                    
                    # Elimina in ordine inverso per evitare problemi con gli indici
                    for idx in sorted(indici_da_eliminare, reverse=True):
                        st.session_state.etf_data.pop(idx)
                    
                    save_data()
                    st.success(f"✅ {len(indici_da_eliminare)} transazioni eliminate!")
                    st.rerun()
    else:
        st.info("ℹ️ Nessuna transazione salvata. Usa il form sopra per aggiungerne una.")

# Sezione Metriche (placeholder)
def render_metriche():
    st.header("📐 Metriche Avanzate")
    
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
            st.plotly_chart(fig, width='stretch')

# Sezione Rendimento Annuo (placeholder)
def render_rendimento_annuo():
    st.header("📅 Rendimento Annuo")
    
    with st.container():
        st.info("🚧 Sezione in costruzione - Disponibile nella prossima versione")
        
        # Placeholder per performance annuali
        st.subheader("📊 Performance Annuali")
        
        # Dati mock per gli anni
        anni = ['2020', '2021', '2022', '2023', '2024']
        rendimenti = [12.5, 8.2, -5.3, 15.7, 10.2]
        benchmark = [10.1, 7.8, -3.2, 14.3, 9.5]
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Tabella performance
            st.subheader("📋 Dettaglio Annuale")
            df_performance = pd.DataFrame({
                'Anno': anni,
                'Rendimento %': rendimenti,
                'Benchmark %': benchmark,
                'Outperformance': [r - b for r, b in zip(rendimenti, benchmark)]
            })
            st.dataframe(df_performance, width='stretch')
        
        with col2:
            # Grafico a barre
            st.subheader("📈 Confronto Annuale")
            fig = go.Figure(data=[
                go.Bar(name='Portafoglio', x=anni, y=rendimenti),
                go.Bar(name='Benchmark', x=anni, y=benchmark)
            ])
            fig.update_layout(
                barmode='group',
                height=400,
                yaxis_title="Rendimento %",
                xaxis_title="Anno"
            )
            st.plotly_chart(fig, width='stretch')
        
        # Statistiche cumulative
        st.subheader("📊 Statistiche Cumulative")
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        
        with col_stat1:
            st.metric("Rendimento Medio", "8.3%", "2.1% vs benchmark")
        with col_stat2:
            st.metric("Volatilità", "12.7%", "±0.5%")
        with col_stat3:
            st.metric("Anni Positivi", "4/5", "80%")
        with col_stat4:
            st.metric("Max Drawdown", "-8.2%", "2022")

# Sezione Impostazioni
def render_impostazioni():
    st.header("⚙️ Impostazioni")
    
    # Tabs per impostazioni
    tab1, tab2, tab3 = st.tabs(["📁 Importazione Dati", "🔧 Configurazione", "💾 Backup & Ripristino"])
    
    with tab1:
        st.subheader("Caricamento transazioni Directa")
        uploaded_directa = st.file_uploader(
            "Carica file CSV transazioni Directa", 
            type=['csv', 'txt'],
            help="Seleziona il file CSV esportato dalla piattaforma Directa",
            key="directa"
        )
        
        if uploaded_directa is not None:
            try:
                df_directa = pd.read_csv(uploaded_directa)
                st.success(f"✅ File caricato: {uploaded_directa.name}")
                st.write("**Anteprima dati (prime 5 righe):**")
                st.dataframe(df_directa.head(), width='stretch')
                
                # Opzioni per elaborazione
                with st.expander("Opzioni di importazione"):
                    auto_map = st.checkbox("Mappatura automatica colonne", value=True)
                    sovrascrivi = st.checkbox("Sovrascrivi dati esistenti", value=False)
                    
                    if st.button("Elabora e Importa", type="primary"):
                        st.info("Funzionalità di importazione in sviluppo...")
            except Exception as e:
                st.error(f"❌ Errore nel caricamento del file: {str(e)}")
        
        st.divider()
        
        st.subheader("Caricamento dettagli ETF")
        uploaded_etf_details = st.file_uploader(
            "Carica file CSV dettagli ETF", 
            type=['csv'],
            help="File con informazioni aggiuntive sugli ETF (ISIN, Settore, etc.)"
        )
        
        if uploaded_etf_details is not None:
            try:
                df_details = pd.read_csv(uploaded_etf_details)
                st.session_state.etf_details = df_details
                df_details.to_csv(ETF_DETAILS_FILE, index=False)
                st.success(f"✅ File caricato: {uploaded_etf_details.name}")
                st.write("**Anteprima dati:**")
                st.dataframe(df_details.head(), width='stretch')
            except Exception as e:
                st.error(f"❌ Errore nel caricamento del file: {str(e)}")
    
    with tab2:
        st.subheader("Configurazione Applicazione")
        
        # Tema
        tema = st.selectbox(
            "Tema dell'interfaccia",
            ["Light", "Dark", "Auto"],
            index=2,
            help="Seleziona il tema preferito"
        )
        
        # Valuta predefinita
        valuta_default = st.selectbox(
            "Valuta predefinita",
            ["EUR", "USD", "GBP", "CHF"],
            index=0
        )
        
        # Formato data
        formato_data = st.selectbox(
            "Formato data",
            ["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"],
            index=0
        )
        
        # Numero decimali
        decimali = st.slider(
            "Numero di decimali per prezzi",
            min_value=2,
            max_value=6,
            value=4
        )
        
        # Salva configurazione
        if st.button("Salva Configurazione", type="primary"):
            st.success("Configurazione salvata (funzionalità completa in sviluppo)")
    
    with tab3:
        st.subheader("Backup Dati")
        
        col_b1, col_b2 = st.columns(2)
        
        with col_b1:
            st.markdown("**📥 Esporta Dati**")
            if st.session_state.etf_data:
                # Backup JSON
                json_str = json.dumps(st.session_state.etf_data, indent=2, ensure_ascii=False)
                st.download_button(
                    label="Scarica Backup JSON",
                    data=json_str,
                    file_name=f"etf_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    help="Scarica una copia di backup di tutte le transazioni"
                )
                
                # Backup CSV
                if st.session_state.etf_data:
                    df_csv = pd.DataFrame(st.session_state.etf_data)
                    csv_str = df_csv.to_csv(index=False)
                    st.download_button(
                        label="Scarica Backup CSV",
                        data=csv_str,
                        file_name=f"etf_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
            else:
                st.info("Nessun dato da esportare")
        
        with col_b2:
            st.markdown("**📤 Ripristina Dati**")
            backup_file = st.file_uploader(
                "Carica file di backup",
                type=['json', 'csv'],
                help="Carica un file di backup per ripristinare i dati"
            )
            
            if backup_file:
                try:
                    if backup_file.name.endswith('.json'):
                        data = json.load(backup_file)
                    else:
                        df = pd.read_csv(backup_file)
                        data = df.to_dict('records')
                    
                    if st.button("Ripristina da Backup", type="secondary"):
                        st.session_state.etf_data = data
                        save_data()
                        st.success("✅ Dati ripristinati con successo!")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Errore nel ripristino: {str(e)}")
        
        st.divider()
        
        st.subheader("⚡ Azioni Rapide")
        
        col_a1, col_a2 = st.columns(2)
        
        with col_a1:
            if st.button("🔄 Aggiorna Prezzi Correnti", width='stretch'):
                st.info("Funzionalità di aggiornamento prezzi in sviluppo...")
        
        with col_a2:
            if st.button("🧹 Pulisci Dati Test", width='stretch'):
                # Rimuove solo le transazioni di prova
                original_len = len(st.session_state.etf_data)
                st.session_state.etf_data = [
                    t for t in st.session_state.etf_data 
                    if not t.get('Transazione prova', False)
                ]
                new_len = len(st.session_state.etf_data)
                save_data()
                st.success(f"✅ Rimosse {original_len - new_len} transazioni di test")
                st.rerun()
        
        # Reset completo (con conferma)
        st.divider()
        st.subheader("⚠️ Area Pericolosa")
        
        with st.expander("Reset Completo Dati", icon="🚨"):
            st.warning("Questa azione cancella TUTTI i dati e non può essere annullata!")
            conferma = st.text_input(
                "Digita 'CONFERMA RESET' per procedere:",
                placeholder="CONFERMA RESET"
            )
            
            if st.button("🚨 Esegui Reset Completo", type="secondary", disabled=True):
                if conferma == "CONFERMA RESET":
                    st.session_state.etf_data = []
                    st.session_state.etf_details = pd.DataFrame()
                    if os.path.exists(DATA_FILE):
                        os.remove(DATA_FILE)
                    if os.path.exists(ETF_DETAILS_FILE):
                        os.remove(ETF_DETAILS_FILE)
                    st.success("✅ Tutti i dati sono stati resettati!")
                    st.rerun()

# Sezione Simula ETF (placeholder)
def render_simula_etf():
    st.header("🔮 Simula ETF")
    
    with st.container():
        st.info("🚧 Sezione in costruzione - Disponibile nella prossima versione")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📊 Simulatore di Investimento")
            
            # Input per simulazione
            capitale = st.number_input(
                "Capitale iniziale (€)",
                min_value=1000,
                max_value=1000000,
                value=10000,
                step=1000
            )
            
            orizzonte = st.slider(
                "Orizzonte temporale (anni)",
                min_value=1,
                max_value=30,
                value=10
            )
            
            rendimento_atteso = st.slider(
                "Rendimento annuo atteso (%)",
                min_value=-5.0,
                max_value=20.0,
                value=7.0,
                step=0.5
            )
            
            volatilita = st.slider(
                "Volatilità annua attesa (%)",
                min_value=5.0,
                max_value=30.0,
                value=15.0,
                step=0.5
            )
        
        with col2:
            st.subheader("📈 Risultati Proiettati")
            
            # Calcolo semplice
            if st.button("Calcola Proiezione", type="primary"):
                # Calcolo interesse composto
                valore_finale = capitale * ((1 + rendimento_atteso/100) ** orizzonte)
                
                st.metric("Valore finale stimato", f"€{valore_finale:,.0f}")
                st.metric("Rendimento totale", f"{(valore_finale/capitale - 1)*100:.1f}%")
                st.metric("Rendimento medio annuo", f"{rendimento_atteso:.1f}%")
        
        # Grafico placeholder per simulazione
        st.subheader("📊 Andamento Simulato")
        fig = go.Figure()
        
        # Genera dati simulati
        anni = list(range(orizzonte + 1))
        valori = [capitale * ((1 + rendimento_atteso/100) ** anno) for anno in anni]
        
        fig.add_trace(go.Scatter(
            x=anni,
            y=valori,
            mode='lines',
            name='Proiezione',
            line=dict(color='green', width=3)
        ))
        
        # Aggiungi banda di volatilità
        if volatilita > 0:
            upper = [val * (1 + volatilita/100) ** anno for anno, val in enumerate(valori)]
            lower = [val * (1 - volatilita/100) ** anno for anno, val in enumerate(valori)]
            
            fig.add_trace(go.Scatter(
                x=anni + anni[::-1],
                y=upper + lower[::-1],
                fill='toself',
                fillcolor='rgba(0,100,80,0.2)',
                line=dict(color='rgba(255,255,255,0)'),
                name='Banda di volatilità'
            ))
        
        fig.update_layout(
            height=400,
            title="Proiezione dell'investimento",
            xaxis_title="Anni",
            yaxis_title="Valore (€)",
            showlegend=True
        )
        
        st.plotly_chart(fig, width='stretch')

# Navigazione principale con tab list
def main():
    # Header dell'applicazione
    col_logo, col_title = st.columns([1, 5])
    st.title("ETF Portfolio Tracker")
    st.caption("Gestione professionale del tuo portafoglio ETF")
    
    # Linea divisoria
    st.divider()
    
    # Tab list principale
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Dashboard",
        "📝 Gestione ETF", 
        "📐 Metriche",
        "📅 Rendimento Annuo",
        "⚙️ Impostazioni",
        "🔮 simula ETF"
    ])
    
    # Contenuto delle tab
    with tab1:
        render_dashboard()
    
    with tab2:
        render_gestione_etf()
    
    with tab3:
        render_metriche()
    
    with tab4:
        render_rendimento_annuo()
    
    with tab5:
        render_impostazioni()
    
    with tab6:
        render_simula_etf()
    
    # Footer
    st.divider()
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        st.caption(f"© {datetime.now().year} ETF Tracker v1.0")
    with col_f2:
        st.caption(f"Dati aggiornati: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    with col_f3:
        if st.session_state.etf_data:
            st.caption(f"Transazioni: {len(st.session_state.etf_data)}")

if __name__ == "__main__":
    main()
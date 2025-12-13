import streamlit as st
from metrics import calculate_metrics
import pandas as pd
from datetime import datetime
from data_manager import save_etf_data, load_etf_data
from config import INTERMEDIARI
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
                save_etf_data(st.session_state.etf_data)
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
                    
                    save_etf_data(st.session_state.etf_data)
                    st.success(f"✅ {len(indici_da_eliminare)} transazioni eliminate!")
                    st.rerun()
    else:
        st.info("ℹ️ Nessuna transazione salvata. Usa il form sopra per aggiungerne una.")


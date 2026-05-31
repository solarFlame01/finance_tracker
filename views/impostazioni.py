import streamlit as st
import pandas as pd
import os
import json
import numpy as np
import sys
from datetime import datetime
from data_manager import save_etf_data, load_etf_data
from config import DATA_FILE, ETF_DETAILS_FILE
from utils import clean_col_name
sys.path.append('..') # sale di un livello della cartella

def render_impostazioni():
    st.header("⚙️ Impostazioni")
    
    # Tabs per impostazioni
    tab1, tab3 = st.tabs(["📁 Importazione Dati", "💾 Backup & Ripristino"])
    
    with tab1:
        col_a1, col_a2 = st.columns(2)
        
        with col_a1:
            st.subheader("Caricamento transazioni Directa")
            uploaded_directa = st.file_uploader(
                "Carica file CSV transazioni Directa", 
                type=['csv', 'txt'],
                help="Seleziona il file CSV esportato dalla piattaforma Directa",
                key="directa"
            )
            
            if uploaded_directa is not None:
                try:
                    df_directa = pd.read_csv(uploaded_directa, skiprows=9, sep=';', encoding='utf-8-sig', decimal=',', parse_dates=['Data operazione', 'Data valuta'], dayfirst=True)              
                    df_directa = df_directa.replace([np.inf, -np.inf], None).fillna(0)
                    df_directa.columns = [clean_col_name(col) for col in df_directa.columns] # ripulisce i caratteri speciali delle colonne
                    df_directa, sell = handle_sell_data(df_directa)
                    from database import insert_directa_transaction  # Importa la funzione dal modulo database

                    with st.spinner("⏳ Caricamento dati in corso..."):
                        insert_directa_transaction(df_directa.to_dict('records'))
                    st.success(f"✅ File caricato: {uploaded_directa.name}")
                    st.write("**Anteprima dati (prime 5 righe):**")
                    st.dataframe(df_directa.head(), width='stretch')
                        
                except Exception as e:
                    st.error(f"❌ Errore nel caricamento del file: {str(e)}")
                    
            if st.button("🧹 Pulisci Dati Directa", width='stretch'):
                    # Rimuove solo le transazioni di prova
                    st.info("Funzionalità per cancellare dati Directa in sviluppo...")
        with col_a2:
            st.subheader("Caricamento dettagli ETF")
            uploaded_etf_details = st.file_uploader(
                "Carica file CSV dettagli ETF", 
                type=['csv'],
                help="File con informazioni aggiuntive sugli ETF (ISIN, Settore, etc.)"
            )
            
            if uploaded_etf_details is not None:
                try:
                    from database import insert_holdings  # Importa la funzione dal modulo database
                    
                    df_details = pd.read_csv(uploaded_etf_details, sep=';',skiprows=7, encoding='latin-1')
                    # Salva i dettagli caricati nello stato della sessione
                    st.session_state.etf_details = df_details
                    
                    etf_name = uploaded_etf_details.name.split('.')[0] # Nome etf preso dal nome del file
                    
                    with st.spinner("⏳ Caricamento dati in corso..."):
                        insert_holdings(etf_name, df_details.to_dict('records'))
                            
                    st.success(f"✅ File caricato: {uploaded_etf_details.name}")
                    st.write("**Anteprima dati:**")
                    st.dataframe(df_details.head(), width='stretch')
                except Exception as e:
                    st.error(f"❌ Errore nel caricamento del file: {str(e)}")
                    
            if st.button("🧹 Pulisci Dati ETF", width='stretch'):
                st.info("Funzionalità per cancellare dati ETF in sviluppo...")
    
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
                        save_etf_data(st.session_state.etf_data)
                        st.success("✅ Dati ripristinati con successo!")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Errore nel ripristino: {str(e)}")
        
        st.divider()
                
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
                    
def handle_sell_data(df):
    # 1) Ordino tutto per data (serve al FIFO)
    df = df.sort_values("data_operazione")

    # 2) Separo le vendite e rimuovo le righe di vendita dal df principale
    df_vendite = df[df["tipo_operazione"] == "Vendita"].copy()
    df_vendite["profitto"] = 0.0  # Inizializza colonna profitto
    df = df[df["tipo_operazione"] == "Acquisto"].copy()

    # 3) Per ogni vendita, scarico le quantita dagli acquisti dello stesso ticker in FIFO
    for idx_vendita, vendita in df_vendite.iterrows():
        ticker = vendita["ticker"]
        da_vendere = vendita["quantita"]
        prezzo_vendita = vendita["importo_euro"]
        profitto_totale = 0.0

        # solo acquisti dello stesso ticker, in ordine di data (già ordinato sopra)
        mask = (df["ticker"] == ticker)
        idx_acquisti = df[mask].index

        for idx in idx_acquisti:
            if da_vendere <= 0:
                break

            q_acq = df.at[idx, "quantita"]
            prezzo_acq = df.at[idx, "importo_euro"]

            if q_acq > da_vendere:
                # consumo parzialmente questa riga di acquisto
                profitto_parziale = (prezzo_vendita + prezzo_acq) * da_vendere # le vendite sono con il meno, quindi devo sommare
                profitto_totale += profitto_parziale
                df.at[idx, "quantita"] = q_acq - da_vendere
                da_vendere = 0
            else:
                # consumo completamente questa riga di acquisto e la elimino
                profitto_parziale = (prezzo_vendita + prezzo_acq) * q_acq # le vendite sono con il meno, quindi devo sommare
                profitto_totale += profitto_parziale
                da_vendere -= q_acq
                df = df.drop(idx)
        
        # Aggiorna il profitto nella riga di vendita
        df_vendite.at[idx_vendita, "profitto"] = profitto_totale
    
    return df, df_vendite
import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
import sys
sys.path.append('..') # sale di un livello della cartella
from data_manager import save_etf_data, load_etf_data
from config import DATA_FILE, ETF_DETAILS_FILE
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
                from database import insert_holdings  # Importa la funzione dal modulo database
                
                df_details = pd.read_csv(uploaded_etf_details, sep=';')
                st.session_state.etf_details = df_details
                insert_holdings("TEST_ETF", df_details.to_dict('records'))  # Esempio di inserimento nel DB
                
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
                        save_etf_data(st.session_state.etf_data)
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
                save_etf_data(st.session_state.etf_data)
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

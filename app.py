# app.py
import streamlit as st
from datetime import datetime

from config import DATA_FILE, ETF_DETAILS_FILE, INTERMEDIARI
from data_manager import load_etf_data, load_etf_details, load_etf_name

from views.dashboard import render_dashboard
from views.gestione_eft import render_gestione_etf
from views.metriche import render_metriche
from views.rendimento_annuo import render_rendimento_annuo
from views.impostazioni import render_impostazioni
from views.simula_eft import render_simula_etf
from views.sidebar import render_sidebar
# Configurazione pagina
st.set_page_config(
    page_title="ETF Portfolio Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"  # Mostra la sidebar di default
)

# Inizializzazione session state
if 'etf_data' not in st.session_state:
    st.session_state.etf_data = load_etf_data()

if 'etf_details' not in st.session_state:
    st.session_state.etf_details = load_etf_details()  
     
if 'etf_transactions' not in st.session_state:
    from database import get_etf_transaction_updated
    st.session_state.etf_transactions = get_etf_transaction_updated()

if 'bottom_3_etf' not in st.session_state:
    from database import get_bottom_3_etf
    st.session_state.bottom_3_etf = get_bottom_3_etf()

if 'top_3_etf' not in st.session_state:
    from database import get_top_3_etf
    st.session_state.top_3_etf = get_top_3_etf()

if 'portfolio_kpi_etf' not in st.session_state:
    from database import get_portfolio_kpi_etf
    st.session_state.kpi_etf = get_portfolio_kpi_etf()

if 'distribuzione_etf' not in st.session_state:
    from database import get_distribuzione_etf
    st.session_state.distribuzione_etf = get_distribuzione_etf()

if 'distribuzione_settore' not in st.session_state:
    from database import get_distribuzione_settore
    st.session_state.distribuzione_settore = get_distribuzione_settore()

if 'distribuzione_valuta_mercato' not in st.session_state:
    from database import get_distribuzione_valuta_mercato
    st.session_state.distribuzione_valuta_mercato = get_distribuzione_valuta_mercato()

if 'distribuzione_area_geografica' not in st.session_state:
    from database import get_distribuzione_area_geografica
    st.session_state.distribuzione_area_geografica = get_distribuzione_area_geografica()

if 'prezzo_medio_acquisto' not in st.session_state:
    from database import get_prezzo_medio_acquisto
    st.session_state.prezzo_medio_acquisto = get_prezzo_medio_acquisto()

# Navigazione principale con sidebar menu
def main():
    # Inizializzazione session state per la pagina attiva
    if 'page' not in st.session_state:
        st.session_state.page = "dashboard"

    # Sidebar - Menu Principale e Azioni Rapide
    with st.sidebar:                       
         render_sidebar() 
    # Routing basato sulla pagina selezionata
    if st.session_state.page == "dashboard":
        render_dashboard()
    elif st.session_state.page == "gestione_etf":
        render_gestione_etf()
    elif st.session_state.page == "metriche":
        render_metriche()
    elif st.session_state.page == "rendimento_annuo":
        render_rendimento_annuo()
    elif st.session_state.page == "impostazioni":
        render_impostazioni()
    elif st.session_state.page == "simula_etf":
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
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
    

# Navigazione principale con sidebar menu
def main():
    # Inizializzazione session state per la pagina attiva
    if 'page' not in st.session_state:
        st.session_state.page = "dashboard"
    
    # Stili CSS per la sidebar moderna
    st.markdown("""
    <style>
        /* Stili generali sidebar */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        }
        
        /* Header sidebar */
        .sidebar-header {
            font-size: 1.6em;
            font-weight: 700;
            margin-bottom: 25px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            color: white;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        
        /* Menu buttons - stile moderno */
        .menu-button {
            display: block;
            width: 100%;
            padding: 12px 16px;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            color: #e2e8f0;
            border: 2px solid transparent;
            border-radius: 8px;
            font-size: 0.95em;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            text-align: left;
        }
        
        .menu-button:hover {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-color: #667eea;
            transform: translateX(5px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            color: #ffffff;
        }
        
        .menu-button:active {
            transform: translateX(3px);
        }
        
        /* Separatore */
        .sidebar-divider {
            margin: 25px 0;
            border-top: 2px solid rgba(102, 126, 234, 0.3);
        }
        
        /* Titolo sezione azioni rapide */
        .quick-actions-title {
            font-size: 0.9em;
            font-weight: 600;
            color: #667eea;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
            padding-left: 5px;
        }
        
        /* Azioni rapide */
        .action-button {
            display: block;
            width: 100%;
            padding: 10px 14px;
            margin-bottom: 8px;
            background: rgba(102, 126, 234, 0.1);
            color: #cbd5e1;
            border: 1.5px solid rgba(102, 126, 234, 0.2);
            border-radius: 6px;
            font-size: 0.85em;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            text-align: left;
        }
        
        .action-button:hover {
            background: rgba(102, 126, 234, 0.2);
            border-color: #667eea;
            color: #e2e8f0;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
        }
        
        .action-button:active {
            background: rgba(102, 126, 234, 0.3);
        }
        
        /* Nascondere i pulsanti di default di streamlit e farli riapparire al hover */
        button[kind="secondary"] {
            transition: all 0.3s ease;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar - Menu Principale e Azioni Rapide
    with st.sidebar:
        st.markdown("<div class='sidebar-header'>🚀 ETF Tracker</div>", unsafe_allow_html=True)
        
        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
        
        # Menu principale con stili personalizzati
        st.markdown("<p style='color: #94a3b8; font-size: 0.75em; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; padding-left: 5px;'>Navigazione</p>", unsafe_allow_html=True)
        
        col_menu = st.columns(1)
        
        if st.button("📊 Dashboard", use_container_width=True, key="btn_dashboard", help="Vai al Dashboard"):
            st.session_state.page = "dashboard"
        
        if st.button("📝 Gestione ETF", use_container_width=True, key="btn_gestione", help="Gestisci i tuoi ETF"):
            st.session_state.page = "gestione_etf"
        
        if st.button("📐 Metriche", use_container_width=True, key="btn_metriche", help="Visualizza le metriche"):
            st.session_state.page = "metriche"
        
        if st.button("📅 Rendimento Annuo", use_container_width=True, key="btn_rendimento", help="Rendimento per anno"):
            st.session_state.page = "rendimento_annuo"
        
        if st.button("⚙️ Impostazioni", use_container_width=True, key="btn_impostazioni", help="Configura l'app"):
            st.session_state.page = "impostazioni"
        
        if st.button("🔮 Simula ETF", use_container_width=True, key="btn_simula", help="Simula investimenti"):
            st.session_state.page = "simula_etf"
        
        st.markdown("<div class='sidebar-divider'></div>", unsafe_allow_html=True)
        
        # Azioni Rapide
        st.markdown("<div class='quick-actions-title'>⚡ Azioni Rapide</div>", unsafe_allow_html=True)
                
        if st.button("🔄 Aggiorna Prezzi", use_container_width=True, key="btn_update_prices"):
                from database import get_etf_list, insert_update_etf_price
                from finance_info import get_etf_price
                import logging
                
                logger = logging.getLogger(__name__)
                logger.info("Inizio aggiornamento prezzi ETF")
                
                etf_list = get_etf_list()
                logger.info(f"Trovati {len(etf_list)} ETF da aggiornare")
                
                success_count = 0
                for etf in etf_list:
                    etf_ticker = etf.get('etf_ticker') if isinstance(etf, dict) else etf
                    logger.debug(f"Elaborazione ETF: {etf_ticker}")
                    
                    price = get_etf_price(etf_ticker)
                    if price is not None:
                        response = insert_update_etf_price(etf_ticker, price)
                        if response is not None:
                            logger.info(f"Prezzo aggiornato: {etf_ticker} = {price}")
                            success_count += 1
                        else:
                            st.error(f"❌ Impossibile aggiornare il prezzo per {etf_ticker}")
                            logger.error(f"Errore DB per {etf_ticker}")
                    else:
                        st.error(f"❌ Impossibile recuperare il prezzo per {etf_ticker}")
                        logger.warning(f"Prezzo non disponibile per {etf_ticker}")
                
                st.success(f"✅ Prezzi aggiornati")
                logger.info(f"Aggiornamento completato: {success_count}/{len(etf_list)} successi")
        
        if st.button("🧹 Pulisci Directa", use_container_width=True, key="btn_clean_directa"):
                st.info("Funzionalità per cancellare dati Directa in sviluppo...")
        
        if st.button("🧹 Pulisci ETF", use_container_width=True, key="btn_clean_etf"):
            st.info("Funzionalità per cancellare dati ETF in sviluppo...")
    
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
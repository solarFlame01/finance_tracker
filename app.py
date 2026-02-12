# app.py
import streamlit as st
from datetime import datetime
import os, time, hashlib
from pathlib import Path
from datetime import datetime
import streamlit as st
from config import DATA_FILE, ETF_DETAILS_FILE, INTERMEDIARI
from data_manager import load_etf_data, load_etf_details, load_etf_name

from views.dashboard import render_dashboard
from views.gestione_eft import render_gestione_etf
from views.metriche import render_metriche
from views.rendimento_annuo import render_rendimento_annuo
from views.impostazioni import render_impostazioni
from views.simula_eft import render_simula_etf
from views.sidebar import render_sidebar
import logging, sys
# ===== CONFIGURAZIONE LOGGING (PRIMA DI TUTTO) =====
# Crea directory logs
Path("logs").mkdir(exist_ok=True)

# Rimuovi handlers esistenti di Streamlit per evitare conflitti
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Configura logging con file + console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%d/%m/%Y %H:%M:%S',
    force=True  # Sovrascrive qualsiasi config precedente
)
# ✅ SILENZIA LIBRERIE ESTERNE (solo ERROR o superiore)
logging.getLogger("streamlit").setLevel(logging.WARNING)
logging.getLogger("watchdog").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.ERROR)           # ✅ Toglie hpack
logging.getLogger("httpcore").setLevel(logging.ERROR)        # ✅ Toglie httpcore
logging.getLogger("httpx").setLevel(logging.ERROR)           # ✅ Toglie httpx
logging.getLogger("urllib3").setLevel(logging.ERROR)         # ✅ Toglie urllib3
logging.getLogger("requests").setLevel(logging.ERROR)        # ✅ Toglie requests
logging.getLogger("yfinance").setLevel(logging.WARNING)      # ✅ Riduce yfinance
logging.getLogger("peewee").setLevel(logging.WARNING)        # ✅ Se usi Peewee
logging.getLogger("supabase").setLevel(logging.WARNING)      # ✅ Se usi Supabase
# Riduci il rumore di Streamlit stesso (opzionale)
logging.getLogger("streamlit").setLevel(logging.WARNING)
logging.getLogger("watchdog").setLevel(logging.WARNING)

# Logger principale dell'app
logger = logging.getLogger(__name__)
logger.info("🚀 App Streamlit avviata")
# ===== FINE CONFIGURAZIONE LOGGING =====

# Configurazione pagina
st.set_page_config(
    page_title="ETF Portfolio Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"  # Mostra la sidebar di default
)

# Login minimale (come già avevi)
def require_login(ttl: int = 3600):
    """Simple password based login with a short-lived cache.

    A successful login stores a token in the query parameters so that a
    browser refresh within ``ttl`` seconds does not ask for the password
    again.  The password (hashed) is also cached so that re-entering it after
    expiration still works even if the environment variable is no longer
    available.
    """

    # --- helper for query params (compat with older Streamlit) ---
    def _get_qp() -> dict:
        if hasattr(st, "query_params"):
            return {k: v for k, v in st.query_params.items()}
        return {k: v[0] for k, v in st.experimental_get_query_params().items()}

    def _set_qp(**params):
        if hasattr(st, "query_params"):
            st.query_params.clear()
            for k, v in params.items():
                st.query_params[k] = v
        else:
            st.experimental_set_query_params(**params)

    def _clear_qp():
        if hasattr(st, "query_params"):
            st.query_params.clear()
        else:
            st.experimental_set_query_params()

    # ------------------------------------------------------------------
    params = _get_qp()

    # Recupera o memorizza l'hash della password
    pw_hash = st.session_state.get("pw_hash")
    hash_file = Path(".app_pw_hash")
    if not pw_hash and hash_file.exists():
        try:
            pw_hash = hash_file.read_text(encoding="utf-8").strip()
            st.session_state["pw_hash"] = pw_hash
        except Exception:
            pw_hash = None
    if not pw_hash:
        raw = st.secrets.get("APP_PASSWORD") or os.getenv("APP_PASSWORD")
        if raw:
            pw_hash = hashlib.sha256(str(raw).encode()).hexdigest()
            st.session_state["pw_hash"] = pw_hash
            try:
                hash_file.write_text(pw_hash, encoding="utf-8")
            except Exception:
                pass

    if not pw_hash:
        st.error("Password non configurata. Imposta APP_PASSWORD nei Secrets o ENV.")
        st.stop()

    # Verifica token in query params
    token = params.get("auth")
    try:
        exp = float(params.get("exp", 0))
    except Exception:
        exp = 0

    if token == pw_hash and exp > time.time():
        st.session_state.auth_ok = True

    if st.session_state.get("auth_ok"):
        with st.sidebar:
            if st.button("Logout"):
                st.session_state.pop("auth_ok", None)
                _clear_qp()
                st.rerun()
        return True

    # Se il token è scaduto ripulisci i parametri
    if token and exp <= time.time():
        _clear_qp()

    # Form di login
    st.markdown("## 🔒 Accesso richiesto")
    pwd = st.text_input("Password", type="password")
    if st.button("Entra", type="primary"):
        if hashlib.sha256(pwd.encode()).hexdigest() == pw_hash:
            st.session_state.auth_ok = True
            expiry = time.time() + ttl
            _set_qp(auth=pw_hash, exp=str(int(expiry)))
            st.success("Accesso consentito ✅"); st.rerun()
        else:
            st.error("Password errata")
    st.stop()
    
#require_login()
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
    
if 'asset_allocation' not in st.session_state:
    from database import get_asset_allocation
    st.session_state.asset_allocation = get_asset_allocation()
    
if 'rendimento_cedole' not in st.session_state:
    from database import get_rendimento_cedole
    st.session_state.rendimento_cedole = get_rendimento_cedole()
    
if 'bond_transactions' not in st.session_state:
    from database import get_bond_transactions
    st.session_state.bond_transactions = get_bond_transactions()
    
if 'rendimento_annuo' not in st.session_state:
    from database import get_rendimento_annuo
    st.session_state.rendimento_annuo = get_rendimento_annuo()
    
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
import streamlit as st

def render_sidebar():
    with st.sidebar:
        # Header
        st.markdown("""
        <div style='text-align: center; padding: 20px 0;'>
            <h2 style='margin: 0; font-size: 24px;'>📈 ETF Hub</h2>
            <p style='margin: 5px 0; color: #888; font-size: 12px;'>Gestione Intelligente del Portafoglio</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # Sezione Guida Rapida
        st.markdown("""
        <h3 style='font-size: 14px; color: #1f77b4; margin-top: 20px; margin-bottom: 10px;'>
        🎯 COME INIZIARE
        </h3>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        **1. Aggiungi ETF**
        Inserisci ticker e quantità acquistati
        
        **2. Monitora**
        Segui prezzi in tempo reale e performance
        
        **3. Analizza**
        Visualizza rendimenti e allocazione portafoglio
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # Sezione Metriche Chiave
        st.markdown("""
        <h3 style='font-size: 14px; color: #2ca02c; margin-top: 20px; margin-bottom: 10px;'>
        📊 COSA TRACCIAMO
        </h3>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        **Prezzo Medio Acquisto**
        Media ponderata dei tuoi acquisti
        
        **Crescita %**
        Rendimento percentuale per posizione
        
        **Market Value**
        Valore attuale del portafoglio
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # Sezione Suggerimenti
        st.markdown("""
        <h3 style='font-size: 14px; color: #ff7f0e; margin-top: 20px; margin-bottom: 10px;'>
        💡 SUGGERIMENTI
        </h3>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        🟢 **Verde**: Posizione in guadagno
        
        🔴 **Rosso**: Posizione in perdita
        
        ⏱️ Aggiorna i prezzi quotidianamente
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # Footer minimal
        st.markdown("""
        <div style='text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;'>
            <p style='font-size: 11px; color: #999; margin: 0;'>
            ETF Management Platform v1.0
            </p>
        </div>
        """, unsafe_allow_html=True)
    '''with st.sidebar:
            st.header("⚡ Azioni Rapide")
                
            if st.button("🔄 Aggiorna Prezzi Correnti", width='stretch'):
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
                    st.rerun()
                    logger.info(f"Aggiornamento completato: {success_count}/{len(etf_list)} successi")
            
            if st.button("🧹 Pulisci Dati Directa", width='stretch'):
                    # Rimuove solo le transazioni di prova
                    st.info("Funzionalità per cancellare dati Directa in sviluppo...")
            
            if st.button("🧹 Pulisci Dati ETF", width='stretch'):
                st.info("Funzionalità per cancellare dati ETF in sviluppo...")
        '''
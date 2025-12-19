import streamlit as st

def render_sidebar():
    
    with st.sidebar:
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
                    logger.info(f"Aggiornamento completato: {success_count}/{len(etf_list)} successi")
            
            if st.button("🧹 Pulisci Dati Directa", width='stretch'):
                    # Rimuove solo le transazioni di prova
                    st.info("Funzionalità per cancellare dati Directa in sviluppo...")
            
            if st.button("🧹 Pulisci Dati ETF", width='stretch'):
                st.info("Funzionalità per cancellare dati ETF in sviluppo...")
        
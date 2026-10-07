import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, datetime
from database import supabase  # Importa il tuo client supabase


def insert_transaction(data: dict):
    """
    Inserisce una transazione nel database Supabase
    """
    try:
        # Converti le date in formato ISO
        if isinstance(data.get("data_operazione"), date):
            data["data_operazione"] = data["data_operazione"].isoformat()
        if isinstance(data.get("data_valuta"), date):
            data["data_valuta"] = data["data_valuta"].isoformat()
        
        response = supabase.table("transaction").insert(data).execute()
        return True, "Transazione inserita con successo!"
    except Exception as e:
        return False, f"Errore durante l'inserimento: {str(e)}"


def _carica_cedole():
    """Carica lo storico cedole da bond_coupons (con cache in session_state)."""
    dati = st.session_state.get("bond_coupons")
    if dati:
        return dati
    try:
        from database import get_bond_coupons
        dati = get_bond_coupons()
        st.session_state.bond_coupons = dati
        return dati
    except Exception:
        return []


def render_storico_cedole():
    """Sezione: storico cronologico delle cedole obbligazionarie incassate."""
    st.markdown("<div class='section-title'>💰 Storico Cedole Incassate</div>", unsafe_allow_html=True)

    cedole = _carica_cedole()
    if not cedole:
        st.info("Nessuna cedola registrata. Carica un file Directa dalla sezione "
                "Impostazioni per popolare automaticamente lo storico cedole.")
        return

    df = pd.DataFrame(cedole)
    for col in ["importo_lordo_eur", "ritenuta_eur", "importo_netto_eur"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "data_operazione" in df.columns:
        df["data_operazione"] = pd.to_datetime(df["data_operazione"], errors="coerce")

    tot_lordo = float(df["importo_lordo_eur"].sum()) if "importo_lordo_eur" in df else 0.0
    tot_rit = float(df["ritenuta_eur"].sum()) if "ritenuta_eur" in df else 0.0
    tot_netto = float(df["importo_netto_eur"].sum()) if "importo_netto_eur" in df else 0.0
    n_cedole = len(df)
    n_titoli = df["isin"].nunique() if "isin" in df else 0

    # KPI riepilogativi
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("💶 Totale Netto", f"€ {tot_netto:,.2f}")
    with k2:
        st.metric("Totale Lordo", f"€ {tot_lordo:,.2f}")
    with k3:
        st.metric("Ritenute", f"€ {tot_rit:,.2f}")
    with k4:
        st.metric("N° Cedole", f"{n_cedole}", delta=f"{n_titoli} titoli", delta_color="off")

    # Grafico: cedole nette per anno
    if "data_operazione" in df.columns and df["data_operazione"].notna().any():
        df_anno = df.dropna(subset=["data_operazione"]).copy()
        df_anno["anno"] = df_anno["data_operazione"].dt.year
        per_anno = df_anno.groupby("anno")["importo_netto_eur"].sum().reset_index()
        fig = go.Figure(go.Bar(
            x=per_anno["anno"].astype(int).astype(str),
            y=per_anno["importo_netto_eur"],
            marker=dict(color="#2ca02c"),
            text=[f"€ {v:,.2f}" for v in per_anno["importo_netto_eur"]],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Netto: € %{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            height=300, template="plotly_white",
            yaxis=dict(tickprefix="€ "), showlegend=False,
            margin=dict(t=20, b=30, l=60, r=20),
            title="Cedole nette per anno",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Tabella cronologica dettagliata
    df_show = df.sort_values("data_operazione", ascending=False)
    cols = [c for c in ["data_operazione", "ticker", "descrizione",
                        "importo_lordo_eur", "ritenuta_eur", "importo_netto_eur"]
            if c in df_show.columns]
    st.dataframe(
        df_show[cols],
        hide_index=True,
        use_container_width=True,
        column_config={
            "data_operazione": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "ticker": st.column_config.TextColumn("Ticker"),
            "descrizione": st.column_config.TextColumn("Titolo"),
            "importo_lordo_eur": st.column_config.NumberColumn("Lordo €", format="€ %.2f"),
            "ritenuta_eur": st.column_config.NumberColumn("Ritenuta €", format="€ %.2f"),
            "importo_netto_eur": st.column_config.NumberColumn("Netto €", format="€ %.2f"),
        },
    )


def render_bond_tracker():
    st.markdown("<h1 style='text-align: center; margin-bottom: 30px;'>Bond Tracker</h1>", unsafe_allow_html=True)

    render_storico_cedole()
    
    # Seconda tabella: Transazioni Bond
    st.markdown("<div class='section-title'>📊 Transazioni</div>", unsafe_allow_html=True)

    if 'bond_transactions' in st.session_state and st.session_state.bond_transactions:
        df_transactions = pd.DataFrame(st.session_state.bond_transactions)
        
        column_config = {
            "data_operazione": st.column_config.DateColumn(
                "Data Operazione",
                format="DD/MM/YYYY"
            ),
            "data_valuta": st.column_config.DateColumn(
                "Data Valuta",
                format="DD/MM/YYYY"
            ),
            "tipo_operazione": st.column_config.TextColumn("Tipo"),
            "ticker": st.column_config.TextColumn("Ticker"),
            "isin": st.column_config.TextColumn("ISIN"),
            "descrizione": st.column_config.TextColumn("Descrizione"),
            "importo_euro": st.column_config.NumberColumn(
                "Importo (€)",
                format="€ %.2f"
            ),
            "importo_divisa": st.column_config.NumberColumn(
                "Importo Divisa",
                format="%.2f"
            ),
            "divisa": st.column_config.TextColumn("Divisa"),
            "quantita": st.column_config.NumberColumn(
                "Quantità",
                format="%.0f"
            ),
            "intermediario": st.column_config.TextColumn("Intermediario"),
            "protocollo": st.column_config.TextColumn("Protocollo"),
            "riferimento_ordine": st.column_config.TextColumn("Rif. Ordine")
        }
        
        st.dataframe(
            df_transactions,
            column_config=column_config,
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Nessuna transazione disponibile")
    
    st.markdown("<div class='section-title'>➕ Aggiungi Bond </div>", unsafe_allow_html=True)    
    with st.form(key="transaction_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            data_operazione = st.date_input(
                "Data Operazione *",
                value=date.today(),
                format="DD/MM/YYYY",
                help="Data in cui è stata effettuata l'operazione"
            )
            
            data_valuta = st.date_input(
                "Data Valuta",
                value=None,
                format="DD/MM/YYYY",
                help="Data di valuta dell'operazione (opzionale)"
            )
            
            tipo_operazione = st.selectbox(
                "Tipo Operazione",
                options=["Acquisto", "Vendita", "Cedola", "Rimborso"],
                help="Tipo di operazione"
            )
            
            ticker = st.text_input(
                "Ticker *",
                placeholder="es. M.BTP",
                help="Ticker del bond (obbligatorio)"
            )
            
            isin = st.text_input(
                "ISIN",
                placeholder="es. IT0005441883",
                max_chars=12,
                help="Codice ISIN del bond (opzionale)"
            )
            
            descrizione = st.text_input(
                "Descrizione",
                placeholder="es. BTP 2035 1.5%",
                max_chars=255,
                help="Descrizione dell'operazione"
            )
        
        with col2:
            protocollo = st.number_input(
                "Protocollo *",
                min_value=1,
                step=1,
                help="Numero di protocollo dell'operazione (obbligatorio)"
            )
            
            riferimento_ordine = st.text_input(
                "Riferimento Ordine *",
                placeholder="es. ORD-2025-001",
                max_chars=50,
                help="Codice di riferimento dell'ordine (obbligatorio)"
            )
            
            importo_euro = st.number_input(
                "Importo in Euro",
                value=0.0,
                step=0.01,
                format="%.2f",
                help="Importo dell'operazione in Euro (usa valori negativi per acquisti)"
            )
            
            importo_divisa = st.number_input(
                "Importo in Divisa",
                value=0.0,
                step=0.01,
                format="%.2f",
                help="Importo nella divisa originale (opzionale)"
            )
            
            divisa = st.text_input(
                "Divisa",
                value="EUR",
                max_chars=3,
                help="Codice divisa (es. EUR, USD)"
            )
            
            quantita = st.number_input(
                "Quantità",
                value=0.0,
                step=0.01,
                format="%.2f",
                help="Quantità di bond acquistati/venduti"
            )
            
            intermediario = st.selectbox(
                "Intermediario",
                options=["Degiro", "Fineco", "Directa", "Interactive Brokers", "Altro"],
                help="Intermediario attraverso cui è stata effettuata l'operazione"
            )
        
        # Submit button
        submitted = st.form_submit_button("💾 Salva Transazione", use_container_width=True)
        
        if submitted:
            # Validazione campi obbligatori
            if not ticker:
                st.error("⚠️ Il campo Ticker è obbligatorio!")
            elif not riferimento_ordine:
                st.error("⚠️ Il campo Riferimento Ordine è obbligatorio!")
            elif protocollo <= 0:
                st.error("⚠️ Il Protocollo deve essere maggiore di zero!")
            else:
                # Prepara i dati per l'inserimento
                transaction_data = {
                    "data_operazione": data_operazione,
                    "ticker": ticker,
                    "protocollo": int(protocollo),
                    "riferimento_ordine": riferimento_ordine,
                    "tipo_operazione": tipo_operazione,
                }
                
                # Aggiungi campi opzionali solo se valorizzati
                if data_valuta:
                    transaction_data["data_valuta"] = data_valuta
                if isin:
                    transaction_data["isin"] = isin
                if descrizione:
                    transaction_data["descrizione"] = descrizione
                if importo_euro != 0.0:
                    transaction_data["importo_euro"] = importo_euro
                if importo_divisa != 0.0:
                    transaction_data["importo_divisa"] = importo_divisa
                if divisa:
                    transaction_data["divisa"] = divisa
                if quantita != 0.0:
                    transaction_data["quantita"] = quantita
                if intermediario:
                    transaction_data["intermediario"] = intermediario
                
                # Inserisci nel database
                success, message = insert_transaction(transaction_data)
                
                if success:
                    st.success(message)
                    # Ricarica i dati
                    st.session_state.bond_transactions = None  # Force reload
                    st.rerun()
                else:
                    st.error(message)
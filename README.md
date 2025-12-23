# ETF Portfolio Tracker v2

## 📋 Architettura dell'App

### Struttura del Progetto

```
etf_portfolio_tracker_v2/
├── app.py                  # Main app - punto di ingresso Streamlit
├── requirements.txt        # Dipendenze Python
├── README.md              # Questo file
├── data/                  # Cartella dati (creata automaticamente)
│   └── transactions.json  # Transazioni salvate in JSON
└── modules/               # Moduli della app
    ├── __init__.py
    ├── utils.py           # Funzioni utility per dati
    ├── dashboard.py       # Sezione Dashboard
    ├── gestione_etf.py    # Sezione Gestione ETF (form)
    ├── metriche.py        # Sezione Metriche (placeholder)
    ├── rendimento_annuo.py # Sezione Rendimento Annuo (placeholder)
    ├── impostazioni.py    # Sezione Impostazioni (upload file)
    └── simula_etf.py      # Sezione Simulazione (placeholder)
```

---

## 🚀 Come Avviare l'App

### Prerequisiti
- Python 3.8+
- pip (gestore pacchetti Python)

### Installazione

1. **Naviga nella cartella del progetto:**
   ```bash
   cd etf_portfolio_tracker_v2
   ```

2. **Installa le dipendenze:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Avvia l'app:**
   ```bash
   streamlit run app.py
   ```

L'app si aprirà automaticamente nel browser a `http://localhost:8501`

---

## 📱 Sezioni dell'App

### 1. **Dashboard** 📊
- **Funzione:** Visualizzazione riepilogativa del portafoglio
- **Contenuto:**
  - Metriche principali (Investito, Valore corrente, Guadagno/Perdita, ETF unici)
  - Tabella completa con tutte le transazioni
  - Colonne: Ticker, Quantità, Prezzo di acquisto, Prezzo corrente, Costo, Market Value, Crescita %, Valuta, Data acquisto, Emittente
  - Opzione per eliminare transazioni
  - Dati di esempio se nessuna transazione è presente

### 2. **Gestione ETF** 🎯
- **Funzione:** Form per aggiungere/modificare transazioni
- **Campi del form:**
  - Ticker (es. VWRL)
  - Quantità
  - Prezzo di acquisto
  - Prezzo corrente
  - Data di acquisto
  - Valuta (EUR/USD/GBP)
  - Emittente (es. Vanguard)
  - Tassa (%)
  - Intermediario (dropdown: Directa, Fineco, Degiro, InteractiveBrokers, Altro)
  - Spese di acquisto
  - Checkbox "Transazione di prova"
- **Anteprima in tempo reale:** Mostra Costo totale, Valore corrente, Guadagno/Perdita, Crescita %
- **Salvataggio:** I dati sono salvati automaticamente in `data/transactions.json`

### 3. **Metriche** 📈
- **Stato:** Placeholder in costruzione
- **Funzionalità previste:**
  - Analisi di rendimento dettagliata
  - Confronto con benchmark
  - Curve di trend
  - Distribuzione del portafoglio
  - Metriche di volatilità

### 4. **Rendimento Annuo** 📅
- **Stato:** Placeholder in costruzione
- **Funzionalità previste:**
  - Rendimento per anno solare
  - Performance annuali confrontate
  - CAGR (Compound Annual Growth Rate)
  - Best/Worst year analysis
  - Drawdown massimo annuale

### 5. **Impostazioni** ⚙️
- **Funzione:** Gestione file e dati
- **Sottosezioni:**
  - **Caricamento Transazioni Directa:** Upload CSV da Directa con anteprima
  - **Caricamento Dettagli ETF:** Upload CSV con info ETF (ISIN, settore, etc.)
  - **Gestione Dati Locali:** Visualizza e cancella dati salvati
  - **Esporta Dati:** Download come CSV o JSON

### 6. **Simula ETF** 🎲
- **Stato:** Placeholder in costruzione
- **Funzionalità previste:**
  - Simulazione investimenti periodici
  - Proiezioni di crescita
  - Analisi di scenari (best/worst case)
  - Dollar cost averaging (DCA) simulation
  - What-if analysis

---

## 💾 Persistenza Dati

### Formato Archiviazione
I dati sono salvati in **JSON** nel file `data/transactions.json`:

```json
[
  {
    "id": 1,
    "ticker": "VWRL",
    "quantita": 50,
    "prezzo_acquisto": 95.20,
    "data_acquisto": "2024-01-15",
    "prezzo_corrente": 102.50,
    "valuta": "EUR",
    "emittente": "Vanguard",
    "tassa": 0.0,
    "intermediario": "Directa",
    "spese_acquisto": 0.0,
    "transazione_prova": false,
    "created_at": "2024-12-05T10:30:00.000000"
  }
]
```

### Dove sono i dati?
- **Percorso:** `data/transactions.json`
- **Creazione:** La cartella `data/` viene creata automaticamente al primo salvataggio
- **Backup:** Si consiglia di fare backup periodici del file JSON

---

## 🔧 Moduli Principali

### `utils.py`
- `load_transactions()` - Carica transazioni da JSON
- `save_transactions()` - Salva transazioni in JSON
- `add_transaction()` - Aggiunge nuova transazione
- `delete_transaction()` - Elimina transazione per ID
- `get_dataframe_from_transactions()` - Converte in DataFrame con calcoli
- `mock_etf_data()` - Dati di esempio

### `dashboard.py`
- `render_dashboard()` - Visualizza riepilogo e tabella transazioni

### `gestione_etf.py`
- `render_gestione_etf()` - Form per aggiungere transazioni

### `metriche.py`, `rendimento_annuo.py`, `simula_etf.py`
- Placeholder per future implementazioni

### `impostazioni.py`
- `render_impostazioni()` - Gestione file e export/import

---

## 📊 Calcoli Automatici

L'app calcola automaticamente:

| Metrica | Formula |
|---------|---------|
| **Costo** | Quantità × Prezzo di acquisto |
| **Market Value** | Quantità × Prezzo corrente |
| **Crescita %** | ((Prezzo corrente - Prezzo acquisto) / Prezzo acquisto) × 100 |
| **Guadagno/Perdita** | Market Value - Costo |
| **Totale Investito** | Σ Costo di tutte le transazioni |
| **Valore Corrente** | Σ Market Value di tutte le transazioni |

---

## 🎨 Design e Layout

- **Sidebar:** Navigazione main con selectbox radio
- **Layout:** Wide mode per migliore visualizzazione tabelle
- **Colonne:** Uso di `st.columns()` per layout responsive
- **Tabelle:** `st.dataframe()` con `width="stretch"`
- **Metriche:** `st.metric()` per visualizzare valori principali
- **Messaggi:** Info, success, warning, error con icone emoji

---

## 🔐 Considerazioni sulla Sicurezza

- I dati sono salvati localmente in plain JSON
- Non sono implementati sistemi di autenticazione (versione 1.0)
- Per uso in produzione: considera cifratura dei dati sensibili
- Backup regolari consigliati

---

## 🚦 Roadmap Futura

- [ ] Implementare sezione Metriche con grafici
- [ ] Implementare sezione Rendimento Annuo
- [ ] Implementare Simulatore ETF
- [ ] Integrare API per prezzi reali (es. Alpha Vantage, Finnhub)
- [ ] Aggiungere autenticazione utente
- [ ] Database SQL per scalabilità
- [ ] Export PDF report
- [ ] Notifiche alerting
- [ ] Mobile responsive design

---

## 📝 Note di Sviluppo

### Come aggiungere una nuova sezione:

1. Crea nuovo file in `modules/nuova_sezione.py`:
   ```python
   import streamlit as st
   
   def render_nuova_sezione():
       st.header("📌 Nuova Sezione")
       st.write("Contenuto...")
   ```

2. Aggiungi import in `modules/__init__.py`:
   ```python
   from .nuova_sezione import render_nuova_sezione
   ```

3. Aggiungi al router in `app.py`:
   ```python
   elif page == "📌 Nuova Sezione":
       render_nuova_sezione()
   ```

---

## ❓ Troubleshooting

### La app non si avvia
- Verifica di aver installato `streamlit`: `pip install streamlit`
- Controlla di essere nella cartella corretta
- Prova: `streamlit run app.py --logger.level=debug`

### I dati non si salvano
- Verifica che la cartella `data/` sia scrivibile
- Controlla i permessi del file `data/transactions.json`

### Errore di import moduli
- Assicurati che `modules/__init__.py` esista
- Verifica che tutti i file `.py` siano nella cartella `modules/`

---

## 📞 Support

Per domande o problemi, consulta la documentazione di Streamlit:
- https://docs.streamlit.io/
- https://docs.streamlit.io/library/api-reference

---

**Versione:** 1.0  
**Data:** Dicembre 2024  
**Sviluppatore:** AI Assistant

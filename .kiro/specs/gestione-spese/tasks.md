# Implementation Plan: Gestione Spese

## Overview

Il piano implementa la sezione **Gestione Spese** in passi incrementali derivati dal design: prima le migrazioni SQL Supabase (nell'ordine corretto delle FK), poi il layer dati in `database.py`, quindi la logica di dominio pura nel package `spese/` (normalizzazione e chiave naturale, importatore Excel, parser PDF multi-banca con registry, auto-categorizzatore, riconciliatore), poi l'integrazione UI (menu reale in `sidebar.py`, ramo di routing in `app.py`, modulo `views/gestione_spese.py` con i tab) e infine il wiring finale.

Ogni task fa riferimento ai requisiti e, dove applicabile, alle proprietà di correttezza del design. I test property-based usano `hypothesis` (minimo 100 iterazioni, tag `# Feature: gestione-spese, Property N`) e coprono le 20 proprietà sulla logica pura; unit/edge-case, integration (1-3 esempi) e smoke test completano la strategia. Si rispettano i pattern reali del progetto: UPSERT idempotente con `on_conflict` + `ignore_duplicates`, `get_secret`, routing `render_*`, sanitizzazione record con `make_json_serializable`, gestione errori `try/except` + `logging` senza crash.

I sotto-task contrassegnati con `*` sono opzionali (test) e possono essere saltati per un MVP più rapido.

## Tasks

- [x] 1. Preparare dipendenze e struttura dei pacchetti
  - [x] 1.1 Aggiungere le dipendenze a `requirements.txt`
    - Aggiungere `pdfplumber` (parsing estratti conto PDF) e `hypothesis` (test property-based)
    - Mantenere lo stile a dipendenze non pinnate del file esistente o pinnare coerentemente con la policy del progetto al momento dell'installazione
    - _Requirements: 4.1, 4.3_

  - [x] 1.2 Creare lo scheletro del package di dominio `spese/`
    - Creare `spese/__init__.py` e `spese/pdf/__init__.py`
    - Creare i file vuoti dei moduli di dominio: `spese/normalizza.py`, `spese/excel_importer.py`, `spese/categorizzatore.py`, `spese/riconciliatore.py`, `spese/pdf/base.py`, `spese/pdf/registry.py`
    - Creare la cartella dei test `tests/` con `tests/__init__.py`
    - _Requirements: 1.5_

- [x] 2. Creare le migrazioni SQL Supabase (ordine FK: conti, categorie, sotto_categorie, movimenti, mapping)
  - [x] 2.1 Migrazione tabella `conti`
    - Creare `supabase/migrations/<ts1>_create_conti_table.sql` con il file timestamp-prefixed
    - `id bigint generated always as identity` PK, `nome varchar not null`, UNIQUE `conti_nome_key`, CHECK lunghezza > 0, `created_at`/`updated_at` default now(), `comment on table`, `create index if not exists idx_conti_nome`
    - _Requirements: 2.2, 2.10_

  - [x] 2.2 Migrazione tabella `categorie`
    - Creare `supabase/migrations/<ts2>_create_categorie_table.sql`
    - `nome varchar not null`, UNIQUE `categorie_nome_key`, CHECK lunghezza > 0, timestamp, `comment on table`
    - _Requirements: 2.3, 2.10_

  - [x] 2.3 Migrazione tabella `sotto_categorie`
    - Creare `supabase/migrations/<ts3>_create_sotto_categorie_table.sql`
    - `categoria_id bigint not null references public.categorie(id)`, `nome varchar not null`, UNIQUE `sotto_categorie_cat_nome_key` su (categoria_id, nome), CHECK lunghezza > 0, indice `idx_sotto_categorie_categoria`
    - Garantire che ogni sotto-categoria appartenga a esattamente una categoria esistente
    - _Requirements: 2.4, 2.10_

  - [x] 2.4 Migrazione tabella `movimenti`
    - Creare `supabase/migrations/<ts4>_create_movimenti_table.sql`
    - Campi obbligatori: `data_movimento date not null`, `conto_id bigint not null references conti(id)`, `importo_eur numeric not null`, `tipo_movimento varchar not null`, `valuta varchar not null default 'EUR'`, `descrizione_normalizzata varchar not null`
    - Campi facoltativi: `categoria_id` FK → categorie, `sotto_categoria_id` FK → sotto_categorie, `nota`, `descrizione`
    - CHECK `movimenti_tipo_movimento_check` sull'insieme del Glossary: `'Spese','In','Trasferimento ingresso','Trasferimento uscita','Aumento Saldo','Decremento Saldo'`
    - UNIQUE `movimenti_chiave_naturale_key` su (`data_movimento, conto_id, importo_eur, descrizione_normalizzata`)
    - Indici su data, conto, categoria; `comment on table`
    - _Requirements: 2.1, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 5.1_

  - [x] 2.5 Migrazione tabella `mapping_esercente_categoria`
    - Creare `supabase/migrations/<ts5>_create_mapping_esercente_categoria_table.sql`
    - `esercente_normalizzato varchar not null` UNIQUE `mapping_esercente_key`, `categoria_id bigint not null references categorie(id)`, `sotto_categoria_id bigint references sotto_categorie(id)`, indice `idx_mapping_esercente`
    - Garantire al più una voce per esercente normalizzato
    - _Requirements: 6.1, 2.10_

  - [x] 2.6 Smoke test dello schema delle migrazioni
    - Verificare la presenza dei file timestamp-prefixed e del DDL con colonne, NOT NULL, UNIQUE, CHECK e FK attesi (parsing statico del testo SQL)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.7, 2.8, 2.10, 6.1_

- [x] 3. Checkpoint - Verificare lo schema
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implementare la logica pura di normalizzazione e chiave naturale (`spese/normalizza.py`)
  - [x] 4.1 Implementare `normalize_esercente(descrizione) -> str`
    - Regola deterministica: `unidecode` → lowercase → strip → collasso spazi multipli → rimozione token di rumore (es. "pos ", "pagamento ", "carta ", date, numeri di autorizzazione, città/stato finali)
    - Coerente con `clean_col_name` di `utils.py`; usata identica in scrittura e lettura del mapping
    - _Requirements: 6.8_

  - [x] 4.2 Implementare `chiave_naturale_movimento(data_iso, conto, importo_eur, descrizione)`
    - Ritorna la tupla (data, conto, importo_eur arrotondato a 2 decimali, descrizione_normalizzata) oppure `None` se un componente obbligatorio manca o non è calcolabile
    - `descrizione_normalizzata = normalize_esercente(descrizione)`
    - _Requirements: 5.3_

  - [x] 4.3 Property test: normalizzazione deterministica e idempotente
    - **Property 1: Normalizzazione esercente deterministica e idempotente**
    - **Validates: Requirements 6.8**
    - `@settings(max_examples=100)`, generatori di stringhe con accenti/maiuscole/rumore; tag `# Feature: gestione-spese, Property 1`

  - [x] 4.4 Property test: chiave non calcolabile implica scarto
    - **Property 3: Chiave naturale non calcolabile implica scarto**
    - **Validates: Requirements 5.3**
    - Generare movimenti privi di un componente obbligatorio e verificare ritorno `None`; tag `# Feature: gestione-spese, Property 3`

- [x] 5. Implementare le helper di dominio su filtri, ordinamento, saldo ed esclusione trasferimenti (`spese/riconciliatore.py` + helper condivise)
  - [x] 5.1 Implementare `saldo_conto(movimenti_conto) -> float`
    - Somma algebrica con segno degli importi dei movimenti del conto
    - _Requirements: 5.7_

  - [x] 5.2 Implementare le helper pure di visualizzazione: ordinamento per data decrescente, applicazione filtri (conto, categoria, intervallo date estremi inclusi) ed esclusione trasferimenti dai totali
    - Centralizzare il filtro che esclude `tipo_movimento` in (`'Trasferimento ingresso'`, `'Trasferimento uscita'`) per spese/entrate
    - _Requirements: 7.5, 8.1, 8.3, 8.4, 8.5_

  - [x] 5.3 Implementare `rileva_coppie_trasferimento(movimenti)`
    - Individuare coppie (uscita conto A, entrata conto B≠A) con differenza importo = 0 e differenza data = 0 giorni
    - _Requirements: 7.4_

  - [x] 5.4 Implementare `prepara_per_upsert(transazioni, conto)`
    - Calcolare la chiave naturale per ogni transazione; separare in `{validi, scartati}` (chiave non calcolabile → scartato); restituire conteggi e record pronti per l'upsert, mostrando 0 per categorie vuote
    - _Requirements: 5.3, 5.5_

  - [x] 5.5 Property test: saldo conto uguale alla somma dei movimenti
    - **Property 18: Saldo del conto uguale alla somma dei movimenti**
    - **Validates: Requirements 5.7**
    - tag `# Feature: gestione-spese, Property 18`

  - [x] 5.6 Property test: ordinamento per data decrescente
    - **Property 19: Ordinamento dell'elenco per data decrescente**
    - **Validates: Requirements 8.1**
    - tag `# Feature: gestione-spese, Property 19`

  - [x] 5.7 Property test: correttezza dei filtri dell'elenco
    - **Property 20: Correttezza dei filtri dell'elenco**
    - **Validates: Requirements 8.3, 8.4, 8.5**
    - tag `# Feature: gestione-spese, Property 20`

  - [x] 5.8 Property test: esclusione dei trasferimenti dai totali
    - **Property 17: Esclusione dei trasferimenti dai totali**
    - **Validates: Requirements 7.5**
    - tag `# Feature: gestione-spese, Property 17`

  - [x] 5.9 Property test: rilevamento delle coppie di trasferimento
    - **Property 16: Rilevamento delle coppie di trasferimento**
    - **Validates: Requirements 7.4**
    - tag `# Feature: gestione-spese, Property 16`

  - [x] 5.10 Property test: conservazione dei conteggi di riconciliazione
    - **Property 4: Conservazione dei conteggi di import/riconciliazione**
    - **Validates: Requirements 3.9, 5.5**
    - tag `# Feature: gestione-spese, Property 4`

- [x] 6. Implementare l'auto-categorizzatore (`spese/categorizzatore.py`)
  - [x] 6.1 Implementare `categorizza(movimento, mapping) -> dict`
    - Funzione pura: assegna Categoria/Sotto_Categoria se `normalize_esercente(descrizione)` è presente nel mapping; altrimenti lascia categoria `None` e `da_categorizzare=True`
    - Usa il mapping corrente passato in input (riflette l'ultima correzione manuale)
    - _Requirements: 6.2, 6.3, 6.4, 6.7_

  - [x] 6.2 Implementare `aggiorna_mapping_da_correzione(esercente_norm, categoria, sotto_categoria)`
    - Costruire il record di mapping da persistere via upsert quando l'utente crea/corregge una categoria
    - _Requirements: 6.5, 6.6_

  - [x] 6.3 Property test: auto-categorizzazione da mapping corrente
    - **Property 12: Auto-categorizzazione da mapping corrente**
    - **Validates: Requirements 6.2, 6.3, 6.7**
    - tag `# Feature: gestione-spese, Property 12`

  - [x] 6.4 Property test: esercente non mappato resta da categorizzare
    - **Property 13: Esercente non mappato resta da categorizzare**
    - **Validates: Requirements 6.4**
    - tag `# Feature: gestione-spese, Property 13`

- [x] 7. Implementare l'importatore Excel (`spese/excel_importer.py`)
  - [x] 7.1 Implementare `leggi_storico_excel(file)` e la validazione colonne
    - Leggere `.xlsx` con pandas/openpyxl; ritornare `(righe_mappate, colonne_mancanti)`; sollevare errore gestito se il file non è un `.xlsx` valido
    - `COLONNE_ATTESE = ["Periodo","Conto","Categoria","Sotto-categoria","Nota","EUR","Guadagni/Spese","Descrizione","Valuta"]`
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 7.2 Implementare `mappa_riga_a_movimento(riga) -> dict | None`
    - Mappare le colonne storiche sui campi Movimento; convertire `Guadagni/Spese` nel Tipo_Movimento; ritornare `None` se mancano campi obbligatori
    - _Requirements: 3.1, 3.4_

  - [x] 7.3 Implementare `importa_storico(file) -> dict`
    - Orchestrazione pura della preparazione: creazione logica di conti/categorie/sotto-categorie mancanti (delega al layer dati), preparazione record per upsert idempotente, riepilogo `{importati, ignorati_presenti, scartati}`
    - _Requirements: 3.5, 3.6, 3.7, 3.9_

  - [x] 7.4 Property test: mappatura deterministica delle colonne storiche
    - **Property 5: Mappatura deterministica delle colonne storiche Excel**
    - **Validates: Requirements 3.1**
    - tag `# Feature: gestione-spese, Property 5`

  - [x] 7.5 Property test: rilevamento delle colonne mancanti
    - **Property 6: Rilevamento delle colonne mancanti**
    - **Validates: Requirements 3.3**
    - tag `# Feature: gestione-spese, Property 6`

  - [x] 7.6 Unit/edge-case test dell'importatore Excel
    - File non-`.xlsx` interrompe senza salvataggi (3.2); riga senza obbligatori scartata e conteggiata (3.4)
    - _Requirements: 3.2, 3.4_

- [x] 8. Implementare il parser PDF multi-banca (`spese/pdf/`)
  - [x] 8.1 Definire l'interfaccia e il modello dati di estrazione (`spese/pdf/base.py`)
    - `BankStatementParser` (Protocol) con `nome_banca`, `riconosce(testo_pdf) -> bool`, `estrai_movimenti(pdf) -> list[TransazioneEstratta]`
    - Dataclass `TransazioneEstratta(data, descrizione, importo_eur, segno, motivo_esclusione)`
    - _Requirements: 4.3, 4.4, 4.8_

  - [x] 8.2 Implementare il registry dei parser (`spese/pdf/registry.py`)
    - `registra_parser(parser)` e `rileva_parser(testo_pdf) -> BankStatementParser | None` (primo parser che riconosce il formato, altrimenti `None`)
    - _Requirements: 4.4, 4.5_

  - [x] 8.3 Implementare almeno un parser concreto per banca e la mappatura segno → tipo
    - Creare `spese/pdf/<banca>.py` con estrazione di data, descrizione, importo (2 decimali) e segno usando `pdfplumber`; registrarlo nel registry
    - Classificare: segno "uscita" → Tipo_Movimento "Spese", "entrata" → "In"; escludere e annotare transazioni senza data/importo
    - _Requirements: 4.3, 4.4, 4.7, 4.8_

  - [x] 8.4 Property test: round-trip del parser PDF per banca
    - **Property 8: Round-trip del parser PDF per banca**
    - **Validates: Requirements 4.3**
    - Generatori di transazioni + formatter sintetico per banca; tag `# Feature: gestione-spese, Property 8`

  - [x] 8.5 Property test: rilevamento del formato banca
    - **Property 9: Rilevamento del formato banca**
    - **Validates: Requirements 4.4**
    - tag `# Feature: gestione-spese, Property 9`

  - [x] 8.6 Property test: mappatura segno → tipo movimento
    - **Property 10: Mappatura segno → tipo movimento**
    - **Validates: Requirements 4.7**
    - tag `# Feature: gestione-spese, Property 10`

  - [x] 8.7 Unit/edge-case test del parser PDF
    - Formato non riconosciuto → `None`/nessun salvataggio (4.5); transazione senza data/importo esclusa con motivo (4.8)
    - _Requirements: 4.5, 4.8_

- [x] 9. Checkpoint - Verificare la logica di dominio
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implementare il layer dati in `database.py` (UPSERT idempotente, `get_secret`, sanitizzazione, try/except + logging)
  - [x] 10.1 Implementare le funzioni per conti, categorie e sotto-categorie
    - `get_conti`, `upsert_conto(nome)` (on_conflict="nome", ignore_duplicates=True), `get_or_create_conto(nome)`; `get_categorie`, `upsert_categoria(nome)`; `get_sotto_categorie`, `upsert_sotto_categoria(nome, categoria_id)` (on_conflict="categoria_id, nome")
    - Riusare il client `supabase` e `get_secret`; `try/except` con `logging.error` e ritorno neutro
    - _Requirements: 2.2, 2.3, 2.4, 3.5, 3.6, 9.2, 9.3_

  - [x] 10.2 Implementare le funzioni sui movimenti
    - `get_movimenti(conto, categoria, data_da, data_a)` con filtri opzionali, ordine data desc, paginazione `.range()` a pagine di 1000 come `get_etf_history`
    - `upsert_movimenti(movimenti)` con `on_conflict='data_movimento, conto_id, importo_eur, descrizione_normalizzata'`, `ignore_duplicates=True`, record sanitizzati con `make_json_serializable` (Timestamp→isoformat, NaN→None)
    - `update_movimento(movimento_id, campi)`, `delete_movimento(movimento_id)`
    - _Requirements: 2.1, 3.7, 3.8, 5.1, 5.2, 5.4, 8.1, 8.3, 8.4, 8.5, 8.8, 8.10, 9.1, 9.5_

  - [x] 10.3 Implementare `insert_trasferimento(...)` con compensazione
    - Inserire i due movimenti speculari ("Trasferimento uscita" origine, "Trasferimento ingresso" destinazione) con pari importo e data; se il secondo fallisce, rimuovere il primo (rollback per compensazione) e notificare
    - _Requirements: 7.1, 7.2_

  - [x] 10.4 Implementare le funzioni sul mapping esercente→categoria
    - `get_mapping_esercente`, `upsert_mapping_esercente(esercente_norm, categoria_id, sotto_categoria_id)` con `on_conflict='esercente_normalizzato'`, `ignore_duplicates=False` (aggiorna in caso di correzione)
    - _Requirements: 6.1, 6.5, 6.6, 9.1_

  - [x] 10.5 Property test: dedup idempotente sulla chiave naturale (con Supabase mockato)
    - **Property 2: Dedup idempotente sulla Chiave_Naturale_Movimento**
    - **Validates: Requirements 3.7, 3.8, 5.1, 5.2, 5.4**
    - Testare la funzione pura di deduplicazione su chiave naturale con client mockato; tag `# Feature: gestione-spese, Property 2`

  - [x] 10.6 Property test: validazione del valore di Tipo_Movimento
    - **Property 11: Validazione del valore di Tipo_Movimento**
    - **Validates: Requirements 2.5, 2.6**
    - Validazione pura dell'insieme ammesso del Glossary; tag `# Feature: gestione-spese, Property 11`

  - [x] 10.7 Integration test del layer dati (1-3 esempi, Supabase mockato)
    - Creazione automatica conti/categorie mancanti (3.5, 3.6); rollback su fallimento batch e sul secondo lato del trasferimento (5.6, 7.2); upsert mapping da correzione (6.5, 6.6); update/delete movimento (8.8, 8.10); uso esclusivo di Supabase via `get_secret` e gestione errore/irraggiungibilità senza crash (9.1, 9.5)
    - _Requirements: 3.5, 3.6, 5.6, 7.2, 6.5, 6.6, 8.8, 8.10, 9.1, 9.5_

- [x] 11. Integrare la navigazione e il routing
  - [x] 11.1 Aggiungere il menu di navigazione reale in `views/sidebar.py`
    - Introdurre un selettore (`st.radio`/bottoni) con mapping etichetta→chiave che imposta `st.session_state.page`, aggiungendo la voce `"gestione_spese"` e mantenendo il testo-guida attuale sotto il menu
    - Sincronizzare l'indice corrente con `st.session_state.page`; non cambiare le stringhe di routing esistenti; default `"dashboard"`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 11.2 Aggiungere il ramo di routing in `app.py`
    - Import `from views.gestione_spese import render_gestione_spese` e ramo `elif st.session_state.page == "gestione_spese": render_gestione_spese()`
    - _Requirements: 1.2, 1.5_

  - [x] 11.3 Unit test di navigazione e routing
    - Presenza voce di navigazione con etichetta non vuota (1.1), chiave univoca non coincidente con le pagine esistenti (1.2, 1.3), default "dashboard" (1.4), presenza `render_gestione_spese` e ramo di routing (1.5)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 12. Implementare la UI della sezione (`views/gestione_spese.py`)
  - [x] 12.1 Creare `render_gestione_spese` con struttura a tab e isolamento errori
    - Corpo incapsulato in `try/except` con `st.error` che preserva `st.session_state.page`; tab: Movimenti, Import Excel, Import Estratto Conto, Trasferimenti, Saldi
    - _Requirements: 1.5, 1.6_

  - [x] 12.2 Implementare il tab Movimenti (elenco, filtri, editing, eliminazione)
    - Elenco ordinato per data desc con data, conto, categoria, sotto-categoria, descrizione, nota, importo (riusa helper del task 5.2); filtri conto/categoria/intervallo date estremi inclusi; messaggi "nessun movimento" (8.2) e "nessun risultato" (8.6); errore su intervallo date invertito con elenco invariato (8.7)
    - Editing inline con validazione: valori validi → `update_movimento` + conferma (8.8); importo non numerico o data non valida → rifiuto e messaggio, movimento invariato (8.9); eliminazione con conferma (8.10); modifica categoria → aggiornamento mapping via `upsert_mapping_esercente` (8.11 → 6.5/6.6)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 8.11, 9.4_

  - [x] 12.3 Implementare il tab Import Excel
    - `st.file_uploader(type=["xlsx"])`, validazione colonne, chiamata a `importa_storico`, riepilogo importati/ignorati/scartati
    - _Requirements: 3.1, 3.2, 3.3, 3.9, 9.4_

  - [x] 12.4 Implementare il tab Import Estratto Conto (PDF)
    - `st.file_uploader(type=["pdf"])` con limite 20 MB e messaggio di rifiuto per estensione/dimensione senza elaborazione (4.1, 4.2); `st.selectbox` del conto; rilevamento formato (`rileva_parser`), messaggio se formato non riconosciuto (4.5)
    - Anteprima con conteggi importati/esclusi e motivi (4.6, 4.8); proposta coppie trasferimento (7.4); conferma → `upsert_movimenti` idempotente; su successo mostrare saldo conto e conteggi (5.5, 5.7); su fallimento rollback e stato precedente (5.6)
    - _Requirements: 4.1, 4.2, 4.5, 4.6, 4.8, 5.5, 5.6, 5.7, 7.4, 9.4_

  - [x] 12.5 Implementare il tab Trasferimenti e il tab Saldi
    - Trasferimenti: form con validazione conto origine ≠ destinazione e importo > 0 (7.3), registrazione via `insert_trasferimento` (7.1, 7.2), riclassificazione coppia proposta e inserimento lato speculare mancante (7.6)
    - Saldi: saldo per conto via `saldo_conto` (5.7)
    - _Requirements: 5.7, 7.1, 7.2, 7.3, 7.6, 9.4_

  - [x] 12.6 Property test: coppia di trasferimento speculare
    - **Property 14: Coppia di trasferimento speculare**
    - **Validates: Requirements 7.1**
    - Testare la costruzione pura della coppia; tag `# Feature: gestione-spese, Property 14`

  - [x] 12.7 Property test: validazione della registrazione di un trasferimento
    - **Property 15: Validazione della registrazione di un trasferimento**
    - **Validates: Requirements 7.3**
    - tag `# Feature: gestione-spese, Property 15`

  - [x] 12.8 Property test: validazione dell'upload PDF
    - **Property 7: Validazione dell'upload PDF**
    - **Validates: Requirements 4.1, 4.2**
    - Testare la funzione pura di validazione (estensione PDF e dimensione ≤ 20 MB); tag `# Feature: gestione-spese, Property 7`

  - [x] 12.9 Unit/edge-case e smoke test della UI
    - Default valuta EUR (2.9), salvataggio senza sotto-categoria (2.11), anteprima con conteggi (4.6), inserimento lato trasferimento mancante (7.6), conferma operazione entro il flusso (9.4); smoke: presenza `render_gestione_spese` e del ramo di routing (1.5)
    - _Requirements: 2.9, 2.11, 4.6, 7.6, 9.4, 1.5_

- [x] 13. Wiring finale e verifica end-to-end dei componenti
  - [x] 13.1 Collegare importatore Excel, parser PDF, categorizzatore e riconciliatore alle funzioni di `database.py` dentro `render_gestione_spese`
    - Flusso PDF: validazione upload → `rileva_parser` → `estrai_movimenti` → `categorizza` → `prepara_per_upsert` + `rileva_coppie_trasferimento` → anteprima → conferma → `upsert_movimenti` → saldo/conteggi
    - Flusso Excel: `leggi_storico_excel` → `mappa_riga_a_movimento` → creazione conti/categorie mancanti → `upsert_movimenti` → riepilogo
    - Garantire assenza di codice orfano: ogni componente è richiamato dalla UI
    - _Requirements: 3.1, 3.5, 3.6, 3.7, 3.9, 4.3, 4.6, 5.1, 5.5, 5.7, 6.2, 6.4, 7.4_

  - [x] 13.2 Integration test end-to-end dei flussi con Supabase mockato
    - Import Excel completo e import PDF completo (parsing → categorizzazione → riconciliazione → upsert idempotente → conteggi/saldo), verificando idempotenza su ricarico sovrapposto
    - _Requirements: 3.7, 3.8, 5.1, 5.2, 5.4, 5.5, 5.7_

- [x] 14. Checkpoint finale - Verificare l'intera feature
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- I task contrassegnati con `*` sono opzionali (test) e possono essere saltati per un MVP più rapido; i task NON contrassegnati vanno sempre implementati.
- Ogni task fa riferimento a requisiti specifici per la tracciabilità; tutte le 20 proprietà di correttezza del design hanno un task property-based dedicato (P1→4.3, P2→10.5, P3→4.4, P4→5.10, P5→7.4, P6→7.5, P7→12.8, P8→8.4, P9→8.5, P10→8.6, P11→10.6, P12→6.3, P13→6.4, P14→12.6, P15→12.7, P16→5.9, P17→5.8, P18→5.5, P19→5.6, P20→5.7).
- I test property-based usano `hypothesis` con `@settings(max_examples=100)` e il tag `# Feature: gestione-spese, Property N`.
- Unit/edge-case coprono scenari specifici; integration test (1-3 esempi) coprono le interazioni con Supabase; smoke test coprono schema e wiring.
- I checkpoint garantiscono validazione incrementale.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["2.3", "2.4", "2.5"] },
    { "id": 3, "tasks": ["2.6", "4.1", "4.2"] },
    { "id": 4, "tasks": ["4.3", "4.4", "5.1", "5.2", "5.3", "5.4", "6.1", "6.2", "7.1", "7.2", "8.1"] },
    { "id": 5, "tasks": ["5.5", "5.6", "5.7", "5.8", "5.9", "5.10", "6.3", "6.4", "7.3", "7.4", "7.5", "7.6", "8.2", "8.3", "10.1", "10.3", "10.4", "11.1"] },
    { "id": 6, "tasks": ["8.4", "8.5", "8.6", "8.7", "10.2", "11.2"] },
    { "id": 7, "tasks": ["10.5", "10.6", "10.7", "11.3", "12.1"] },
    { "id": 8, "tasks": ["12.2", "12.3", "12.4", "12.5"] },
    { "id": 9, "tasks": ["12.6", "12.7", "12.8", "12.9", "13.1"] },
    { "id": 10, "tasks": ["13.2"] }
  ]
}
```

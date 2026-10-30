# Requirements Document

## Introduction

Questa funzionalità aggiunge all'applicazione (attualmente un tracker di portafoglio investimenti basato su Streamlit) una nuova sezione separata e indipendente chiamata "Gestione Spese". La sezione permette all'utente di registrare, importare, categorizzare, visualizzare e modificare tutte le proprie spese ed entrate personali su più conti.

La sezione introduce tre capacità principali:

1. Un modello dati su Supabase per movimenti, conti e categorie, coerente con lo storico spese già mantenuto dall'utente in un file Excel (2226 righe).
2. L'import automatico di estratti conto in formato PDF provenienti da banche diverse (formati eterogenei), con riconciliazione e deduplicazione dei movimenti.
3. L'auto-categorizzazione dei movimenti basata sull'esercente riconosciuto, con un mapping esercente→categoria persistito su Supabase e aggiornabile dalle correzioni manuali dell'utente.

La sezione deve integrarsi con l'architettura esistente: nuova voce di navigazione nella sidebar e routing in `app.py` basato su `st.session_state.page`, funzioni di accesso dati centralizzate in `database.py` con pattern UPSERT idempotente su chiavi naturali, migrazioni SQL timestamp-prefixed in `supabase/migrations/`.

## Glossary

- **App**: L'applicazione Streamlit esistente, nella sua interezza.
- **Sezione_Gestione_Spese**: La nuova area funzionale dedicata alla gestione delle spese personali, distinta dall'area di tracking investimenti.
- **Movimento**: Una singola registrazione finanziaria con data, conto, categoria, sotto-categoria, nota, importo in EUR, tipo movimento, descrizione e valuta.
- **Tipo_Movimento**: La classificazione del movimento. Valori ammessi: "Spese", "In" (entrata), "Trasferimento ingresso", "Trasferimento uscita", "Aumento Saldo", "Decremento Saldo".
- **Conto**: Un'entità che rappresenta un conto finanziario dell'utente (es. BBVA, Revolut, N26, Poste, Contanti).
- **Categoria**: Un'etichetta di classificazione del movimento (es. "🏡 Casa", "🚙 Auto", "💶 Stipendio"), inclusa la possibilità di categorie tecniche di riconciliazione ("Allineamento conto", "Modifica Saldo", "Storno").
- **Sotto_Categoria**: Una suddivisione opzionale di una Categoria (es. Categoria "🚙 Auto" → Sotto_Categoria "Diesel").
- **Trasferimento**: Un movimento di denaro tra due Conti dell'utente, registrato come due Movimenti speculari: un "Trasferimento uscita" dal conto di origine e un "Trasferimento ingresso" nel conto di destinazione.
- **Importatore_Excel**: Il componente che importa lo storico spese dal file Excel esistente verso Supabase.
- **Parser_PDF**: Il componente che estrae i Movimenti dal PDF di un estratto conto bancario.
- **Riconciliatore**: Il componente che allinea i Movimenti estratti da un estratto conto con quelli già presenti su Supabase, deduplicando ed evitando inserimenti ripetuti.
- **Esercente**: Il soggetto o la controparte di un Movimento, derivato dalla descrizione della transazione (es. nome del negozio o del beneficiario).
- **Esercente normalizzato**: La forma canonica di un Esercente prodotta applicando alla descrizione della transazione la regola di normalizzazione deterministica dell'Auto_Categorizzatore; funge da chiave del Mapping_Esercente_Categoria.
- **Mapping_Esercente_Categoria**: La corrispondenza persistita tra un Esercente normalizzato e la Categoria (ed eventuale Sotto_Categoria) di default da assegnargli.
- **Auto_Categorizzatore**: Il componente che assegna automaticamente Categoria e Sotto_Categoria a un Movimento in base al Mapping_Esercente_Categoria.
- **Chiave_Naturale_Movimento**: L'insieme di campi che identifica univocamente un Movimento ai fini della deduplicazione (data, conto, importo in EUR, descrizione normalizzata).
- **Database**: L'istanza Supabase (PostgreSQL) dell'applicazione.
- **Utente**: La persona che utilizza l'App.

## Requirements

### Requirement 1: Accesso alla sezione separata Gestione Spese

**User Story:** Come Utente, voglio una sezione separata dedicata alle spese, distinta dal tracking investimenti, così da gestire le mie finanze personali senza confonderle con il portafoglio.

#### Acceptance Criteria

1. THE App SHALL mostrare nel menu principale della sidebar una sola voce di navigazione dedicata alla Sezione_Gestione_Spese, con etichetta non vuota.
2. WHEN l'Utente seleziona la voce di navigazione della Sezione_Gestione_Spese, THE App SHALL impostare st.session_state.page a una stringa identificativa univoca non coincidente con quella delle pagine esistenti ed entro 2 secondi visualizzare la relativa pagina.
3. WHILE l'Utente visualizza la Sezione_Gestione_Spese, THE App SHALL mostrare esclusivamente contenuti relativi alle spese personali e NON renderizzare le pagine di tracking investimenti (dashboard, gestione_etf, metriche, rendimento_annuo, simula_etf, prossimo_pac, proiezioni_future).
4. WHILE st.session_state.page non è ancora stato impostato, THE App SHALL visualizzare la pagina predefinita "dashboard".
5. THE Sezione_Gestione_Spese SHALL essere implementata come funzione render_* in un singolo modulo dedicato dentro views/, con un ramo di routing su st.session_state.page in app.py.
6. IF il rendering della Sezione_Gestione_Spese fallisce, THEN THE App SHALL mostrare all'Utente un messaggio di errore e preservare lo stato di navigazione corrente.

### Requirement 2: Modello dati dei movimenti su Supabase

**User Story:** Come Utente, voglio che i miei movimenti siano salvati su Supabase in una struttura coerente con il mio storico, così da avere un'unica fonte dati affidabile.

#### Acceptance Criteria

1. THE Database SHALL fornire una tabella dei Movimenti con campi obbligatori (data del movimento, riferimento al Conto, importo in EUR, Tipo_Movimento, valuta) e campi facoltativi (riferimento alla Categoria, riferimento alla Sotto_Categoria, nota, descrizione).
2. THE Database SHALL fornire una tabella dei Conti in cui il nome di ogni Conto è univoco e non vuoto.
3. THE Database SHALL fornire una tabella delle Categorie in cui il nome di ogni Categoria è univoco e non vuoto.
4. THE Database SHALL fornire una tabella delle Sotto_Categorie in cui ogni Sotto_Categoria è associata a esattamente una Categoria esistente.
5. WHEN un Movimento viene salvato, THE Database SHALL registrare il valore del Tipo_Movimento solo se appartiene all'insieme di valori definito nel Glossary per Tipo_Movimento.
6. IF il Tipo_Movimento di un Movimento non appartiene all'insieme definito nel Glossary, THEN THE Database SHALL rifiutare il salvataggio senza modificare i dati esistenti.
7. IF un Movimento riferisce un Conto, una Categoria o una Sotto_Categoria non esistente, THEN THE Database SHALL rifiutare il salvataggio del Movimento.
8. IF un campo obbligatorio del Movimento è mancante, THEN THE Database SHALL rifiutare il salvataggio del Movimento.
9. WHEN un Movimento viene salvato senza valuta specificata, THE Database SHALL registrare la valuta con valore predefinito "EUR".
10. THE Movimento SHALL essere definito tramite una migrazione SQL timestamp-prefixed collocata in supabase/migrations/.
11. WHERE un Movimento non ha una Sotto_Categoria assegnata, THE Database SHALL consentire il salvataggio del Movimento con la Sotto_Categoria assente.

### Requirement 3: Import e migrazione dello storico spese dal file Excel

**User Story:** Come Utente, voglio importare il mio storico spese dal file Excel esistente su Supabase, così da non perdere i dati accumulati e partire con lo storico completo.

#### Acceptance Criteria

1. WHEN l'Utente carica un file .xlsx dello storico spese nella Sezione_Gestione_Spese, THE Importatore_Excel SHALL leggere le righe e mappare le colonne Periodo, Conto, Categoria, Sotto-categoria, Nota, EUR, Guadagni/Spese, Descrizione e Valuta sui campi del Movimento.
2. IF il file caricato non può essere letto come file .xlsx valido, THEN THE Importatore_Excel SHALL interrompere l'import senza salvare alcun Movimento e mostrare all'Utente un messaggio di errore.
3. IF il file caricato non contiene le colonne attese dallo schema dello storico, THEN THE Importatore_Excel SHALL interrompere l'import senza salvare alcun Movimento e mostrare all'Utente un messaggio che indica le colonne mancanti.
4. IF una riga del file non contiene i campi obbligatori del Movimento, THEN THE Importatore_Excel SHALL ignorare quella riga e conteggiarla tra le righe scartate.
5. WHEN l'Importatore_Excel incontra un Conto non ancora presente nella tabella dei Conti, THE Importatore_Excel SHALL creare il Conto prima di salvare il Movimento.
6. WHEN l'Importatore_Excel incontra una Categoria o una Sotto_Categoria non ancora presente, THE Importatore_Excel SHALL creare la Categoria o la Sotto_Categoria prima di salvare il Movimento.
7. WHEN l'Importatore_Excel salva i Movimenti importati, THE Database SHALL eseguire un UPSERT idempotente sulla Chiave_Naturale_Movimento.
8. IF un Movimento importato ha la stessa Chiave_Naturale_Movimento di un Movimento già presente, THEN THE Database SHALL mantenere un solo record senza creare duplicati.
9. WHEN l'import è completato, THE Importatore_Excel SHALL mostrare all'Utente il numero di Movimenti importati, il numero di Movimenti ignorati perché già presenti e il numero di righe scartate perché non valide.

### Requirement 4: Upload e parsing di estratti conto PDF di banche diverse

**User Story:** Come Utente, voglio caricare il PDF dell'estratto conto di banche diverse, così da registrare i movimenti senza inserirli manualmente.

#### Acceptance Criteria

1. THE Sezione_Gestione_Spese SHALL fornire un controllo di upload che accetta un singolo file con estensione PDF di dimensione massima 20 MB.
2. IF il file caricato ha un'estensione diversa da PDF oppure supera i 20 MB, THEN THE Sezione_Gestione_Spese SHALL rifiutare il file e mostrare all'Utente un messaggio che indica il motivo del rifiuto, senza avviare l'elaborazione.
3. WHEN l'Utente carica un estratto conto PDF e seleziona il Conto associato, THE Parser_PDF SHALL estrarre da ogni transazione la data, la descrizione, l'importo come valore numerico con 2 decimali e il segno (entrata o uscita).
4. WHERE il formato del PDF corrisponde a una banca supportata, THE Parser_PDF SHALL applicare le regole di estrazione specifiche di quella banca.
5. IF il formato del PDF caricato non corrisponde ad alcuna banca supportata, THEN THE Parser_PDF SHALL interrompere l'elaborazione, non salvare alcun Movimento e mostrare all'Utente un messaggio che indica che il formato non è riconosciuto.
6. WHEN il Parser_PDF completa l'estrazione, THE Sezione_Gestione_Spese SHALL mostrare all'Utente l'anteprima dei Movimenti estratti, indicando il numero di transazioni importate e il numero di transazioni escluse, prima del salvataggio definitivo.
7. WHEN il Parser_PDF determina il segno di una transazione, THE Parser_PDF SHALL assegnare Tipo_Movimento "Spese" alle uscite e Tipo_Movimento "In" alle entrate, salvo riclassificazione come Trasferimento secondo il Requirement 7.
8. IF una transazione del PDF non contiene una data o un importo estraibili, THEN THE Parser_PDF SHALL escludere quella transazione dall'import e segnalarla all'Utente nell'anteprima con l'indicazione del motivo dell'esclusione.

### Requirement 5: Riconciliazione e deduplicazione dei movimenti

**User Story:** Come Utente, voglio che il caricamento di un estratto conto allinei automaticamente il conto senza creare duplicati, così da poter ricaricare estratti sovrapposti in sicurezza.

#### Acceptance Criteria

1. WHEN il Riconciliatore salva i Movimenti estratti da un estratto conto, THE Database SHALL eseguire un UPSERT idempotente sulla Chiave_Naturale_Movimento, in modo che ripetere il salvataggio degli stessi Movimenti non alteri il numero totale di Movimenti presenti.
2. IF un Movimento estratto ha la stessa Chiave_Naturale_Movimento di un Movimento già presente, THEN THE Riconciliatore SHALL conservare invariati i valori del Movimento esistente senza crearne un duplicato.
3. IF un Movimento estratto non consente di calcolare la Chiave_Naturale_Movimento, THEN THE Riconciliatore SHALL scartare quel Movimento e conteggiarlo tra gli scartati.
4. WHEN l'Utente ricarica un estratto conto che copre un periodo sovrapposto a uno già importato, THE Riconciliatore SHALL inserire soltanto i Movimenti non ancora presenti.
5. WHEN la riconciliazione di un estratto conto è completata senza errori, THE Riconciliatore SHALL mostrare all'Utente il numero di Movimenti nuovi inseriti, il numero di Movimenti già presenti ignorati e il numero di Movimenti scartati, mostrando 0 per ogni categoria priva di Movimenti.
6. IF durante la riconciliazione di un estratto conto il salvataggio su Database fallisce, THEN THE Riconciliatore SHALL annullare le modifiche parziali e preservare lo stato dei Movimenti precedente alla riconciliazione.
7. WHEN la riconciliazione di un estratto conto è completata senza errori, THE Riconciliatore SHALL calcolare e mostrare all'Utente il saldo del Conto risultante dalla somma dei Movimenti di quel Conto.

### Requirement 6: Auto-categorizzazione per esercente

**User Story:** Come Utente, voglio che le transazioni dello stesso esercente ricevano automaticamente la stessa categoria già usata in passato, così da ridurre l'etichettatura manuale.

#### Acceptance Criteria

1. THE Database SHALL fornire una tabella Mapping_Esercente_Categoria che associa a ogni Esercente normalizzato al più una voce, con una Categoria di default obbligatoria e una Sotto_Categoria di default facoltativa.
2. WHEN l'Auto_Categorizzatore elabora un Movimento il cui Esercente normalizzato corrisponde a una voce del Mapping_Esercente_Categoria, THE Auto_Categorizzatore SHALL assegnare al Movimento la Categoria di default di quella voce.
3. WHERE la voce corrispondente del Mapping_Esercente_Categoria ha una Sotto_Categoria di default, WHEN l'Auto_Categorizzatore assegna la Categoria di default, THE Auto_Categorizzatore SHALL assegnare anche la Sotto_Categoria di default.
4. IF l'Esercente normalizzato di un Movimento non corrisponde ad alcuna voce del Mapping_Esercente_Categoria, THEN THE Auto_Categorizzatore SHALL lasciare il Movimento senza Categoria assegnata e contrassegnarlo come da categorizzare.
5. WHEN l'Utente assegna o corregge manualmente la Categoria di un Movimento il cui Esercente non è presente nel Mapping_Esercente_Categoria, THE App SHALL creare una nuova voce del Mapping_Esercente_Categoria per quell'Esercente con la Categoria e la Sotto_Categoria indicate.
6. WHEN l'Utente corregge manualmente la Categoria di un Movimento il cui Esercente è già presente nel Mapping_Esercente_Categoria, THE App SHALL aggiornare la voce esistente con la nuova Categoria e la nuova Sotto_Categoria.
7. WHEN una voce del Mapping_Esercente_Categoria è stata aggiornata o creata da una azione manuale dell'Utente, THE Auto_Categorizzatore SHALL utilizzare la voce corrente per i Movimenti elaborati successivamente per lo stesso Esercente.
8. THE Auto_Categorizzatore SHALL normalizzare l'Esercente a partire dalla descrizione della transazione tramite una regola deterministica che produce lo stesso Esercente normalizzato in fase di scrittura e di lettura del Mapping_Esercente_Categoria.

### Requirement 7: Gestione dei trasferimenti tra conti

**User Story:** Come Utente, voglio che i trasferimenti tra i miei conti siano gestiti come coppia di movimenti speculari, così che i saldi dei conti e i totali delle spese restino corretti.

#### Acceptance Criteria

1. WHEN un Trasferimento viene registrato tra due Conti distinti dell'Utente, THE App SHALL creare due Movimenti speculari con pari importo e pari data valuta: un Movimento con Tipo_Movimento "Trasferimento uscita" sul Conto di origine e un Movimento con Tipo_Movimento "Trasferimento ingresso" sul Conto di destinazione.
2. IF durante la registrazione di un Trasferimento la creazione di uno dei due Movimenti speculari non va a buon fine, THEN THE App SHALL annullare anche l'altro Movimento della coppia, non modificare i saldi dei Conti coinvolti e presentare all'Utente un messaggio di errore che indica il fallimento della registrazione del Trasferimento.
3. IF il Conto di origine e il Conto di destinazione di un Trasferimento coincidono, oppure l'importo del Trasferimento non è maggiore di 0, THEN THE App SHALL rifiutare la registrazione del Trasferimento e presentare all'Utente un messaggio di errore che indica la causa del rifiuto, senza creare alcun Movimento.
4. WHEN il Riconciliatore individua, tra i Movimenti estratti da un estratto conto, un Movimento di uscita da un Conto e un Movimento di entrata in un altro Conto dell'Utente con differenza di importo pari a 0 e differenza di data pari a 0 giorni, THE Riconciliatore SHALL proporre all'Utente la riclassificazione della coppia come Trasferimento.
5. WHILE un Movimento ha Tipo_Movimento "Trasferimento ingresso" o "Trasferimento uscita", THE App SHALL escludere quel Movimento sia dal totale delle spese sia dal totale delle entrate in tutte le visualizzazioni di spesa.
6. IF tra i Movimenti presenti esiste un solo lato di un Trasferimento, THEN THE App SHALL consentire all'Utente di registrare il lato speculare mancante con pari importo e pari data valuta sul Conto opposto.

### Requirement 8: Visualizzazione, filtro e modifica manuale dei movimenti

**User Story:** Come Utente, voglio visualizzare, filtrare e modificare i miei movimenti categorizzati, così da controllarli e correggerli dall'interfaccia.

#### Acceptance Criteria

1. WHEN l'Utente apre la Sezione_Gestione_Spese, THE App SHALL mostrare l'elenco dei Movimenti ordinati per data in ordine decrescente, con data, Conto, Categoria, Sotto_Categoria, descrizione, nota e importo in EUR.
2. IF all'apertura della Sezione_Gestione_Spese non esiste alcun Movimento, THEN THE App SHALL mostrare un messaggio che indica l'assenza di Movimenti e nessuna riga nell'elenco.
3. WHEN l'Utente applica un filtro per Conto, THE App SHALL mostrare soltanto i Movimenti del Conto selezionato.
4. WHEN l'Utente applica un filtro per Categoria, THE App SHALL mostrare soltanto i Movimenti della Categoria selezionata.
5. WHEN l'Utente applica un filtro per intervallo di date, THE App SHALL mostrare soltanto i Movimenti con data compresa nell'intervallo selezionato, estremi inclusi.
6. IF nessun Movimento soddisfa i filtri applicati, THEN THE App SHALL mostrare un messaggio che indica l'assenza di risultati e nessuna riga nell'elenco.
7. IF l'Utente applica un filtro per intervallo di date con data iniziale successiva alla data finale, THEN THE App SHALL rifiutare il filtro, mostrare un messaggio di errore che indica l'intervallo non valido e mantenere invariato l'elenco dei Movimenti visualizzato.
8. WHEN l'Utente modifica un campo di un Movimento e conferma la modifica con valori validi, THE Database SHALL aggiornare il Movimento corrispondente con i nuovi valori e THE App SHALL mostrare un messaggio di conferma dell'avvenuto aggiornamento.
9. IF l'Utente conferma una modifica con un importo non numerico o con una data in formato non valido, THEN THE App SHALL rifiutare la modifica, mostrare un messaggio di errore che indica il campo non valido e mantenere invariato il Movimento nel Database.
10. WHEN l'Utente conferma l'eliminazione di un Movimento, THE Database SHALL rimuovere il Movimento corrispondente e THE App SHALL mostrare un messaggio di conferma dell'avvenuta eliminazione.
11. WHEN l'Utente modifica la Categoria di un Movimento dall'elenco, THE App SHALL applicare l'aggiornamento del Mapping_Esercente_Categoria secondo il Requirement 6.

### Requirement 9: Persistenza su Supabase

**User Story:** Come Utente, voglio che tutti i dati della gestione spese siano salvati su Supabase, così da ritrovarli su ogni dispositivo e in modo coerente con il resto dell'App.

#### Acceptance Criteria

1. WHEN l'Utente conferma la creazione, la modifica o l'eliminazione di Movimenti, Conti, Categorie, Sotto_Categorie o voci del Mapping_Esercente_Categoria, THE App SHALL eseguire l'operazione esclusivamente nel Database Supabase.
2. THE App SHALL accedere ai dati della Sezione_Gestione_Spese tramite funzioni centralizzate nel modulo database.py, coerentemente con il pattern esistente.
3. THE App SHALL recuperare le credenziali Supabase tramite la funzione get_secret esistente in database.py.
4. WHEN un'operazione sul Database viene completata con successo, THE App SHALL mostrare all'Utente una conferma dell'esito entro 2 secondi.
5. IF un'operazione sul Database fallisce o il Database resta irraggiungibile per più di 10 secondi, THEN THE App SHALL registrare l'errore nel log, preservare i dati inseriti dall'Utente senza applicare modifiche parziali e mostrare un messaggio di errore senza interrompere l'esecuzione dell'App.

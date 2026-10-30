# views/gestione_spese.py
"""Sezione Gestione Spese.

Punto di ingresso `render_gestione_spese` con struttura a tab. L'intero corpo
e' protetto da try/except per non rompere la navigazione: in caso di eccezione
si mostra un messaggio di errore e si preserva `st.session_state.page`
(Req 1.5, 1.6).

I corpi dei singoli tab sono qui definiti come helper interni stub: le
implementazioni dettagliate vengono aggiunte dai task 12.2-12.5.
"""

import logging
from datetime import date, datetime

import streamlit as st

import database
import spese.pdf  # noqa: F401 - import per registrare i parser PDF nel registry
from spese import riconciliatore
from spese.categorizzatore import categorizza
from spese.excel_importer import (
    COLONNE_ATTESE,
    ExcelNonValido,
    importa_storico,
    leggi_storico_excel,
)
from spese.normalizza import normalize_esercente
from spese.pdf.registry import rileva_parser
from spese.riconciliatore import (
    prepara_per_upsert,
    rileva_coppie_trasferimento,
    saldo_conto,
)

logger = logging.getLogger(__name__)

# Limite di dimensione per l'upload dell'estratto conto PDF: 20 MB (Req 4.1/4.2).
_PDF_MAX_BYTES = 20 * 1024 * 1024

# Mappatura segno -> Tipo_Movimento per le transazioni estratte dal PDF
# (Req 4.7): le uscite diventano "Spese", le entrate "In".
_SEGNO_TIPO_MOVIMENTO = {"uscita": "Spese", "entrata": "In"}


def render_gestione_spese() -> None:
    """Punto di ingresso della sezione. Orchestrazione a tab:

    - Tab "Movimenti": elenco + filtri + editing/eliminazione inline (Req 8)
    - Tab "Import Excel": upload storico .xlsx (Req 3)
    - Tab "Import Estratto Conto": upload PDF + selezione conto + anteprima (Req 4,5)
    - Tab "Trasferimenti": registrazione/riclassificazione coppie (Req 7)
    - Tab "Saldi": saldo per conto (Req 5.7)

    L'intero corpo e' protetto da try/except per non rompere la navigazione
    (Req 1.6): su eccezione mostra `st.error` e lascia invariato
    `st.session_state.page`.
    """
    try:
        st.header("💶 Gestione Spese")

        tab_movimenti, tab_excel, tab_estratto, tab_trasferimenti, tab_saldi = st.tabs(
            [
                "Movimenti",
                "Import Excel",
                "Import Estratto Conto",
                "Trasferimenti",
                "Saldi",
            ]
        )

        with tab_movimenti:
            _tab_movimenti()

        with tab_excel:
            _tab_import_excel()

        with tab_estratto:
            _tab_import_estratto_conto()

        with tab_trasferimenti:
            _tab_trasferimenti()

        with tab_saldi:
            _tab_saldi()

    except Exception as e:
        # Isolamento errori di rendering (Req 1.6): non modifichiamo
        # st.session_state.page, preservando lo stato di navigazione corrente.
        logger.error("Errore nel rendering di Gestione Spese: %s", e, exc_info=True)
        st.error(
            "Si è verificato un errore durante il caricamento della sezione "
            "Gestione Spese. La navigazione è stata preservata."
        )


def _tab_movimenti() -> None:
    """Tab Movimenti: elenco, filtri, editing ed eliminazione (Req 8).

    Mostra l'elenco dei Movimenti ordinato per data decrescente con data,
    conto, categoria, sotto-categoria, descrizione, nota e importo (Req 8.1),
    riusando le helper pure del task 5.2
    (`riconciliatore.ordina_per_data_desc`, `riconciliatore.applica_filtri`).

    Offre filtri per conto, categoria e intervallo date (estremi inclusi,
    Req 8.3/8.4/8.5). Quando non esiste alcun Movimento mostra "nessun
    movimento" (Req 8.2); quando i filtri non producono risultati mostra
    "nessun risultato" (Req 8.6); un intervallo date invertito
    (data_da > data_a) viene rifiutato con un messaggio di errore lasciando
    l'elenco invariato (Req 8.7).

    L'editing inline valida importo e data: valori validi -> `update_movimento`
    + conferma (Req 8.8); importo non numerico o data non valida -> rifiuto con
    messaggio e movimento invariato (Req 8.9). L'eliminazione richiede conferma
    esplicita (Req 8.10). La modifica della categoria aggiorna il
    Mapping_Esercente_Categoria via `upsert_mapping_esercente` (Req 8.11).
    """
    # 1) Recupero dati di supporto (nomi di conti / categorie / sotto-categorie)
    #    per arricchire i movimenti grezzi (che contengono solo gli *_id) e per
    #    popolare i filtri e gli editor. Tutte le chiamate DB sono difensive:
    #    in caso di errore le helper di database.py ritornano liste vuote.
    conti = database.get_conti() or []
    categorie = database.get_categorie() or []
    sotto_categorie = database.get_sotto_categorie() or []

    conto_by_id = {c.get("id"): c.get("nome") for c in conti if isinstance(c, dict)}
    categoria_by_id = {
        c.get("id"): c.get("nome") for c in categorie if isinstance(c, dict)
    }
    categoria_id_by_nome = {
        c.get("nome"): c.get("id") for c in categorie if isinstance(c, dict)
    }
    sotto_by_id = {
        s.get("id"): s.get("nome") for s in sotto_categorie if isinstance(s, dict)
    }
    # (nome sotto-categoria, categoria_id) -> id, per risolvere la sotto-categoria
    sotto_id_by_nome_cat = {
        (s.get("nome"), s.get("categoria_id")): s.get("id")
        for s in sotto_categorie
        if isinstance(s, dict)
    }

    # 2) Elenco completo dei movimenti (ordine data desc gia' lato DB, ma lo
    #    riapplichiamo con la helper pura per coerenza col task 5.2 / Req 8.1).
    movimenti_raw = database.get_movimenti() or []

    # Req 8.2: nessun Movimento nello store -> messaggio e nessuna riga.
    if not movimenti_raw:
        st.info("Nessun movimento presente.")
        return

    movimenti = [
        _arricchisci_movimento(m, conto_by_id, categoria_by_id, sotto_by_id)
        for m in movimenti_raw
        if isinstance(m, dict)
    ]
    movimenti = riconciliatore.ordina_per_data_desc(movimenti)

    # 3) Filtri (conto, categoria, intervallo date).
    st.subheader("Filtri")
    col_conto, col_cat = st.columns(2)
    with col_conto:
        nomi_conti = sorted({v for v in conto_by_id.values() if v})
        conto_sel = st.selectbox(
            "Conto", options=["(Tutti)"] + nomi_conti, index=0, key="mov_filtro_conto"
        )
    with col_cat:
        nomi_categorie = sorted({v for v in categoria_by_id.values() if v})
        categoria_sel = st.selectbox(
            "Categoria",
            options=["(Tutte)"] + nomi_categorie,
            index=0,
            key="mov_filtro_categoria",
        )

    col_da, col_a, col_attiva = st.columns([2, 2, 1])
    with col_attiva:
        usa_date = st.checkbox("Filtra per date", value=False, key="mov_filtro_date_on")
    with col_da:
        data_da = st.date_input(
            "Da", value=None, key="mov_filtro_data_da", disabled=not usa_date
        )
    with col_a:
        data_a = st.date_input(
            "A", value=None, key="mov_filtro_data_a", disabled=not usa_date
        )

    conto_filtro = None if conto_sel == "(Tutti)" else conto_sel
    categoria_filtro = None if categoria_sel == "(Tutte)" else categoria_sel

    data_da_iso = None
    data_a_iso = None
    intervallo_invalido = False
    if usa_date and data_da is not None and data_a is not None:
        # Req 8.7: intervallo invertito -> rifiuto, elenco invariato.
        if data_da > data_a:
            intervallo_invalido = True
        else:
            data_da_iso = data_da.isoformat()
            data_a_iso = data_a.isoformat()
    elif usa_date:
        if data_da is not None:
            data_da_iso = data_da.isoformat()
        if data_a is not None:
            data_a_iso = data_a.isoformat()

    st.divider()

    if intervallo_invalido:
        # Rifiuto del filtro: mostriamo l'errore e l'elenco resta invariato
        # (nessun filtro per data applicato).
        st.error(
            "Intervallo di date non valido: la data iniziale è successiva alla "
            "data finale. Il filtro per date non è stato applicato."
        )
        movimenti_filtrati = riconciliatore.applica_filtri(
            movimenti, conto=conto_filtro, categoria=categoria_filtro
        )
    else:
        movimenti_filtrati = riconciliatore.applica_filtri(
            movimenti,
            conto=conto_filtro,
            categoria=categoria_filtro,
            data_da=data_da_iso,
            data_a=data_a_iso,
        )

    # Req 8.6: nessun risultato per i filtri applicati.
    if not movimenti_filtrati:
        st.warning("Nessun risultato per i filtri applicati.")
        return

    # 4) Elenco + editing inline.
    st.subheader("Movimenti")
    _mostra_editor_movimenti(
        movimenti_filtrati,
        nomi_categorie=nomi_categorie,
        categoria_id_by_nome=categoria_id_by_nome,
        sotto_categorie=sotto_categorie,
        sotto_id_by_nome_cat=sotto_id_by_nome_cat,
    )


def _arricchisci_movimento(
    movimento: dict,
    conto_by_id: dict,
    categoria_by_id: dict,
    sotto_by_id: dict,
) -> dict:
    """Aggiunge i nomi (conto, categoria, sotto_categoria) a un movimento grezzo.

    I movimenti restituiti da `database.get_movimenti` contengono solo gli id
    delle entità collegate (`conto_id`, `categoria_id`, `sotto_categoria_id`).
    Questa funzione produce una copia arricchita con i campi testuali `conto`,
    `categoria` e `sotto_categoria` richiesti sia dalle helper di filtro/ordine
    (`applica_filtri` lavora sui nomi) sia dalla visualizzazione (Req 8.1).
    """
    arricchito = dict(movimento)
    arricchito["conto"] = conto_by_id.get(movimento.get("conto_id"))
    arricchito["categoria"] = categoria_by_id.get(movimento.get("categoria_id"))
    arricchito["sotto_categoria"] = sotto_by_id.get(
        movimento.get("sotto_categoria_id")
    )
    return arricchito


def _mostra_editor_movimenti(
    movimenti: list,
    nomi_categorie: list,
    categoria_id_by_nome: dict,
    sotto_categorie: list,
    sotto_id_by_nome_cat: dict,
) -> None:
    """Renderizza l'editor inline dei movimenti con validazione e azioni DB.

    Mostra una riga per Movimento con i campi editabili (data, categoria,
    sotto-categoria, descrizione, nota, importo) e una colonna "Elimina".
    Alla conferma valida importo e data (Req 8.9) e applica gli aggiornamenti
    via `update_movimento` (Req 8.8), l'eventuale aggiornamento del mapping
    esercente (Req 8.11) e le eliminazioni confermate (Req 8.10).
    """
    try:
        import pandas as pd
    except Exception as e:  # pragma: no cover - pandas è dipendenza del progetto
        logger.error("pandas non disponibile per l'editor movimenti: %s", e)
        st.error("Impossibile mostrare l'elenco dei movimenti.")
        return

    # Costruiamo la tabella editabile. Teniamo da parte lo stato originale per
    # confrontare i valori e capire cosa è cambiato alla conferma.
    righe = []
    originali_by_id = {}
    for m in movimenti:
        mid = m.get("id")
        originali_by_id[mid] = m
        righe.append(
            {
                "id": mid,
                "data": _to_date(m.get("data_movimento")),
                "conto": m.get("conto") or "",
                "categoria": m.get("categoria") or "",
                "sotto_categoria": m.get("sotto_categoria") or "",
                "descrizione": m.get("descrizione")
                or m.get("descrizione_normalizzata")
                or "",
                "nota": m.get("nota") or "",
                "importo_eur": m.get("importo_eur"),
                "Elimina": False,
            }
        )

    df = pd.DataFrame(
        righe,
        columns=[
            "id",
            "data",
            "conto",
            "categoria",
            "sotto_categoria",
            "descrizione",
            "nota",
            "importo_eur",
            "Elimina",
        ],
    )

    opzioni_categoria = [""] + list(nomi_categorie)

    edited = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        key="mov_editor",
        disabled=["id", "conto"],
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "data": st.column_config.DateColumn("Data"),
            "conto": st.column_config.TextColumn("Conto", disabled=True),
            "categoria": st.column_config.SelectboxColumn(
                "Categoria", options=opzioni_categoria
            ),
            "sotto_categoria": st.column_config.TextColumn("Sotto-categoria"),
            "descrizione": st.column_config.TextColumn("Descrizione"),
            "nota": st.column_config.TextColumn("Nota"),
            "importo_eur": st.column_config.NumberColumn("Importo (€)", format="%.2f"),
            "Elimina": st.column_config.CheckboxColumn("Elimina"),
        },
    )

    if not st.button("💾 Salva modifiche", type="primary", key="mov_salva"):
        return

    _applica_modifiche(
        edited=edited,
        originali_by_id=originali_by_id,
        categoria_id_by_nome=categoria_id_by_nome,
        sotto_id_by_nome_cat=sotto_id_by_nome_cat,
    )


def _applica_modifiche(
    edited,
    originali_by_id: dict,
    categoria_id_by_nome: dict,
    sotto_id_by_nome_cat: dict,
) -> None:
    """Valida le righe modificate e applica update/delete + mapping sul DB.

    Separa le righe marcate per l'eliminazione (Req 8.10) dalle righe
    aggiornate. Per ogni aggiornamento valida importo (numerico) e data
    (formato valido): se la validazione fallisce la riga viene rifiutata con un
    messaggio e NON viene toccata sul DB (Req 8.9). Per le righe valide applica
    `update_movimento` (Req 8.8) e, se la categoria è cambiata, aggiorna il
    mapping esercente via `upsert_mapping_esercente` (Req 8.11 -> 6.5/6.6).
    """
    aggiornati = 0
    eliminati = 0
    errori: list[str] = []

    try:
        righe_iter = edited.to_dict(orient="records")
    except Exception:
        # Fallback difensivo se `edited` non è un DataFrame.
        righe_iter = list(edited)

    for riga in righe_iter:
        mid = riga.get("id")
        originale = originali_by_id.get(mid)
        if originale is None:
            continue

        # Req 8.10: eliminazione (il checkbox è la conferma esplicita per riga).
        if riga.get("Elimina"):
            try:
                res = database.delete_movimento(mid)
            except Exception as e:  # difensivo: nessun crash (Req 9.5)
                logger.error("Errore delete movimento id=%s: %s", mid, e)
                res = None
            if res is None:
                errori.append(f"ID {mid}: eliminazione non riuscita.")
            else:
                eliminati += 1
            continue

        # Validazione importo (Req 8.9): deve essere numerico.
        importo_valido, importo_val = _valida_importo(riga.get("importo_eur"))
        if not importo_valido:
            errori.append(f"ID {mid}: importo non numerico, modifica rifiutata.")
            continue

        # Validazione data (Req 8.9): deve essere una data valida.
        data_valida, data_iso = _valida_data(riga.get("data"))
        if not data_valida:
            errori.append(f"ID {mid}: data non valida, modifica rifiutata.")
            continue

        # Risoluzione categoria -> id e sotto-categoria -> id.
        categoria_nome = (riga.get("categoria") or "").strip() or None
        categoria_id = (
            categoria_id_by_nome.get(categoria_nome)
            if categoria_nome is not None
            else None
        )
        sotto_nome = (riga.get("sotto_categoria") or "").strip() or None
        sotto_id = (
            sotto_id_by_nome_cat.get((sotto_nome, categoria_id))
            if sotto_nome is not None
            else None
        )

        campi = {
            "data_movimento": data_iso,
            "importo_eur": importo_val,
            "categoria_id": categoria_id,
            "sotto_categoria_id": sotto_id,
            "descrizione": (riga.get("descrizione") or "").strip() or None,
            "nota": (riga.get("nota") or "").strip() or None,
        }

        try:
            res = database.update_movimento(mid, campi)
        except Exception as e:  # difensivo (Req 9.5)
            logger.error("Errore update movimento id=%s: %s", mid, e)
            res = None

        if res is None:
            errori.append(f"ID {mid}: aggiornamento non riuscito.")
            continue

        aggiornati += 1

        # Req 8.11: se la categoria è cambiata, aggiorna il mapping esercente.
        categoria_orig = originale.get("categoria")
        if categoria_nome != categoria_orig and categoria_id is not None:
            descrizione_src = (
                originale.get("descrizione")
                or originale.get("descrizione_normalizzata")
                or ""
            )
            esercente_norm = normalize_esercente(descrizione_src)
            if esercente_norm:
                try:
                    database.upsert_mapping_esercente(
                        esercente_norm, categoria_id, sotto_id
                    )
                except Exception as e:  # difensivo (Req 9.5)
                    logger.error(
                        "Errore upsert mapping esercente '%s': %s", esercente_norm, e
                    )

    # Messaggi di conferma / errore (Req 8.8, 8.9, 8.10, 9.4).
    if aggiornati:
        st.success(f"✅ {aggiornati} movimento/i aggiornato/i.")
    if eliminati:
        st.success(f"🗑️ {eliminati} movimento/i eliminato/i.")
    for messaggio in errori:
        st.error(messaggio)

    if aggiornati or eliminati:
        st.rerun()


def _to_date(valore):
    """Converte un valore ISO / date / datetime in `datetime.date` o None."""
    if valore is None or valore == "":
        return None
    if isinstance(valore, datetime):
        return valore.date()
    if isinstance(valore, date):
        return valore
    try:
        return datetime.strptime(str(valore)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _valida_importo(valore):
    """Valida un importo (Req 8.9). Ritorna (ok, valore_float).

    Accetta int/float/stringa numerica (con virgola o punto decimale). Rifiuta
    None, NaN e stringhe non convertibili.
    """
    if valore is None:
        return False, None
    if isinstance(valore, bool):
        return False, None
    if isinstance(valore, (int, float)):
        if valore != valore:  # NaN
            return False, None
        return True, float(valore)
    try:
        testo = str(valore).strip().replace(",", ".")
        if testo == "":
            return False, None
        importo = float(testo)
    except (TypeError, ValueError):
        return False, None
    if importo != importo:  # NaN
        return False, None
    return True, importo


def _valida_data(valore):
    """Valida una data (Req 8.9). Ritorna (ok, data_iso_str)."""
    convertita = _to_date(valore)
    if convertita is None:
        return False, None
    return True, convertita.isoformat()


def _tab_import_excel() -> None:
    """Tab Import Excel: upload storico .xlsx (Req 3).

    Flusso:

    1. `st.file_uploader(type=["xlsx"])` per caricare lo storico spese
       (Req 3.1). Finché non c'è un file, nessuna azione.
    2. Alla presenza di un file si esegue subito la validazione delle colonne
       via `leggi_storico_excel`: un file non leggibile come `.xlsx` solleva
       `ExcelNonValido` e viene mostrato un errore senza salvare nulla
       (Req 3.2); se mancano colonne attese le si segnala all'Utente e l'import
       non prosegue (Req 3.3).
    3. Solo quando la validazione va a buon fine si mostra un pulsante di
       conferma; alla pressione si chiama `importa_storico` e si mostra il
       riepilogo `{importati, ignorati_presenti, scartati}` (Req 3.9) con una
       conferma dell'esito (Req 9.4).

    L'intero corpo è protetto da try/except per non far crashare la UI: in caso
    di errore imprevisto si mostra `st.error` e si logga (coerente con Req 9.5).
    """
    st.subheader("Import storico spese (Excel)")
    st.caption(
        "Carica il file `.xlsx` dello storico spese. Colonne attese: "
        + ", ".join(COLONNE_ATTESE)
        + "."
    )

    file = st.file_uploader(
        "File storico spese (.xlsx)",
        type=["xlsx"],
        key="excel_uploader",
    )

    if file is None:
        return

    try:
        # 1) Validazione preliminare: leggibilità del file e presenza colonne.
        #    `leggi_storico_excel` solleva ExcelNonValido su file illeggibile
        #    (Req 3.2) e ritorna le colonne mancanti (Req 3.3).
        try:
            _righe, colonne_mancanti = leggi_storico_excel(file)
        except ExcelNonValido as e:
            # Req 3.2: file non valido -> nessun salvataggio, messaggio di errore.
            st.error(f"❌ {e}")
            return

        if colonne_mancanti:
            # Req 3.3: colonne attese assenti -> import interrotto, elenco colonne.
            st.error(
                "❌ Il file non contiene tutte le colonne attese. "
                "Colonne mancanti: " + ", ".join(colonne_mancanti) + "."
            )
            return

        st.success(
            f"✅ File valido: {len(_righe)} riga/e rilevata/e. "
            "Premi «Importa» per salvare i movimenti su Supabase."
        )

        # 2) Conferma esplicita prima del salvataggio definitivo.
        if not st.button("⬆️ Importa", type="primary", key="excel_importa"):
            return

        # 3) Import vero e proprio. Il file va "riavvolto" perché la lettura di
        #    validazione ha consumato il buffer dell'uploader.
        try:
            file.seek(0)
        except Exception:  # alcuni buffer non supportano seek: non è bloccante
            pass

        with st.spinner("Import in corso…"):
            riepilogo = importa_storico(file)

        importati = riepilogo.get("importati", 0)
        ignorati = riepilogo.get("ignorati_presenti", 0)
        scartati = riepilogo.get("scartati", 0)

        # Req 3.9 + 9.4: riepilogo con conferma dell'esito.
        st.success("✅ Import completato.")
        col_imp, col_ign, col_sca = st.columns(3)
        col_imp.metric("Importati", importati)
        col_ign.metric("Ignorati (già presenti)", ignorati)
        col_sca.metric("Scartati (non validi)", scartati)

    except ExcelNonValido as e:
        # Difesa aggiuntiva: se `importa_storico` risolleva ExcelNonValido.
        st.error(f"❌ {e}")
    except Exception as e:  # difensivo: non far crashare la UI (Req 9.5)
        logger.error("Errore durante l'import Excel: %s", e, exc_info=True)
        st.error(
            "Si è verificato un errore durante l'import del file Excel. "
            "Nessun dato è stato modificato."
        )


def _carica_mapping_esercente() -> dict[str, dict]:
    """Costruisce il mapping esercente->categoria per l'auto-categorizzazione.

    Legge le voci del Mapping_Esercente_Categoria via
    `database.get_mapping_esercente` (Req 6.1) e risolve `categoria_id` /
    `sotto_categoria_id` nei rispettivi nomi tramite `database.get_categorie`
    e `database.get_sotto_categorie`. Il risultato è un dizionario keyed by
    `esercente_normalizzato` nel formato atteso da
    `spese.categorizzatore.categorizza` (voci con chiavi `categoria` e
    `sotto_categoria`), così da assegnare automaticamente le categorie ai
    movimenti estratti dall'estratto conto (Req 6.2, 6.4).

    Tutte le chiamate DB sono difensive: in caso di errore le helper ritornano
    liste vuote e questa funzione restituisce un mapping vuoto (nessun
    movimento auto-categorizzato, Req 9.5).
    """
    voci = database.get_mapping_esercente() or []
    categorie = database.get_categorie() or []
    sotto_categorie = database.get_sotto_categorie() or []

    categoria_by_id = {
        c.get("id"): c.get("nome") for c in categorie if isinstance(c, dict)
    }
    sotto_by_id = {
        s.get("id"): s.get("nome") for s in sotto_categorie if isinstance(s, dict)
    }

    mapping: dict[str, dict] = {}
    for voce in voci:
        if not isinstance(voce, dict):
            continue
        esercente = voce.get("esercente_normalizzato")
        if not esercente:
            continue
        mapping[esercente] = {
            "categoria": categoria_by_id.get(voce.get("categoria_id")),
            "sotto_categoria": sotto_by_id.get(voce.get("sotto_categoria_id")),
        }
    return mapping


def _valida_upload_pdf(file) -> str | None:
    """Valida l'upload dell'estratto conto PDF (Req 4.1/4.2).

    Controlla estensione (`.pdf`) e dimensione (<= 20 MB). Ritorna ``None`` se
    il file è valido, altrimenti una stringa con il motivo del rifiuto da
    mostrare all'Utente senza avviare alcuna elaborazione.
    """
    nome = getattr(file, "name", "") or ""
    if not nome.lower().endswith(".pdf"):
        return "Estensione non valida: è richiesto un file con estensione .pdf."

    dimensione = getattr(file, "size", None)
    if dimensione is not None and dimensione > _PDF_MAX_BYTES:
        mb = dimensione / (1024 * 1024)
        return (
            f"File troppo grande ({mb:.1f} MB): la dimensione massima consentita "
            "è 20 MB."
        )
    return None


def _estrai_testo_pdf(file) -> str:
    """Estrae il testo da un PDF caricato usando ``pdfplumber`` (import lazy).

    Unico punto di I/O del tab: legge tutte le pagine e ne concatena il testo,
    usato sia per il rilevamento del formato (`rileva_parser`) sia come input
    del parser riconosciuto. In caso di errore di lettura ritorna stringa vuota.
    """
    import pdfplumber

    try:
        file.seek(0)
    except Exception:  # alcuni buffer non supportano seek: non è bloccante
        pass

    with pdfplumber.open(file) as documento:
        return "\n".join(
            (pagina.extract_text() or "") for pagina in documento.pages
        )


def _tab_import_estratto_conto() -> None:
    """Tab Import Estratto Conto: upload PDF + selezione conto + anteprima (Req 4, 5).

    Flusso completo:

    1. `st.file_uploader(type=["pdf"])` con validazione estensione/dimensione
       (<= 20 MB). Un file non conforme viene rifiutato con il motivo e senza
       alcuna elaborazione (Req 4.1, 4.2).
    2. `st.selectbox` per selezionare il Conto a cui associare i Movimenti.
    3. Estrazione del testo del PDF e rilevamento del formato banca con
       `rileva_parser`: se nessun parser riconosce il formato si mostra
       "formato non riconosciuto" e si interrompe senza salvare (Req 4.5).
    4. Estrazione dei Movimenti, classificazione segno -> Tipo_Movimento
       (Req 4.7), anteprima con conteggi importati/esclusi e motivi di
       esclusione (Req 4.6, 4.8) e proposta delle coppie di Trasferimento
       (Req 7.4).
    5. Conferma esplicita -> `upsert_movimenti` idempotente. Su successo mostra
       il saldo del Conto e i conteggi (Req 5.5, 5.7); su fallimento mostra un
       messaggio di rollback con lo stato precedente preservato (Req 5.6).

    L'intero corpo è protetto da try/except per non far crashare la UI (Req 9.5).
    """
    st.subheader("Import estratto conto (PDF)")
    st.caption(
        "Carica il PDF dell'estratto conto (max 20 MB) e seleziona il conto a "
        "cui associare i movimenti. Il formato della banca viene riconosciuto "
        "automaticamente."
    )

    try:
        # --- 1) Upload + validazione (Req 4.1, 4.2) ---------------------------
        file = st.file_uploader(
            "File estratto conto (.pdf)",
            type=["pdf"],
            key="pdf_uploader",
        )

        if file is None:
            return

        motivo_rifiuto = _valida_upload_pdf(file)
        if motivo_rifiuto is not None:
            # Req 4.2: rifiuto con motivo, nessuna elaborazione.
            st.error(f"❌ {motivo_rifiuto}")
            return

        # --- 2) Selezione del conto ------------------------------------------
        conti = database.get_conti() or []
        nomi_conti = sorted(
            {c.get("nome") for c in conti if isinstance(c, dict) and c.get("nome")}
        )
        conto_id_by_nome = {
            c.get("nome"): c.get("id") for c in conti if isinstance(c, dict)
        }

        if not nomi_conti:
            st.warning(
                "Nessun conto disponibile. Crea prima un conto (es. tramite "
                "l'import dello storico Excel) per poter importare l'estratto."
            )
            return

        conto_sel = st.selectbox(
            "Conto associato",
            options=nomi_conti,
            key="pdf_conto",
        )

        # --- 3) Estrazione testo + rilevamento formato (Req 4.4, 4.5) --------
        with st.spinner("Lettura del PDF in corso…"):
            testo_pdf = _estrai_testo_pdf(file)

        parser = rileva_parser(testo_pdf)
        if parser is None:
            # Req 4.5: formato non riconosciuto -> stop, nessun salvataggio.
            st.error(
                "❌ Formato dell'estratto conto non riconosciuto. Nessun "
                "movimento è stato elaborato."
            )
            return

        st.info(f"Formato riconosciuto: **{getattr(parser, 'nome_banca', 'banca')}**.")

        # --- 4) Estrazione movimenti + anteprima (Req 4.6, 4.7, 4.8) ---------
        transazioni = parser.estrai_movimenti(testo_pdf) or []

        importabili = [t for t in transazioni if t.motivo_esclusione is None]
        escluse = [t for t in transazioni if t.motivo_esclusione is not None]

        col_imp, col_esc = st.columns(2)
        col_imp.metric("Transazioni importabili", len(importabili))
        col_esc.metric("Transazioni escluse", len(escluse))

        if escluse:
            # Req 4.8: segnalazione delle transazioni escluse con il motivo.
            with st.expander(f"Transazioni escluse ({len(escluse)})"):
                for t in escluse:
                    data_txt = t.data.isoformat() if t.data is not None else "—"
                    st.write(
                        f"- {data_txt} · {t.descrizione or '(senza descrizione)'} "
                        f"→ {t.motivo_esclusione}"
                    )

        if not importabili:
            st.warning(
                "Nessuna transazione importabile dall'estratto conto. "
                "Nessun movimento verrà salvato."
            )
            return

        # Classificazione segno -> Tipo_Movimento e costruzione delle
        # transazioni grezze per l'anteprima e l'upsert (Req 4.7). L'importo
        # porta il segno (uscita negativa, entrata positiva) così che saldo e
        # rilevamento delle coppie di trasferimento siano corretti.
        transazioni_dict = []
        for t in importabili:
            tipo_movimento = _SEGNO_TIPO_MOVIMENTO.get(t.segno, "Spese")
            importo_con_segno = (
                -abs(t.importo_eur) if t.segno == "uscita" else abs(t.importo_eur)
            )
            transazioni_dict.append(
                {
                    "data_movimento": t.data.isoformat(),
                    "descrizione": t.descrizione,
                    "importo_eur": importo_con_segno,
                    "tipo_movimento": tipo_movimento,
                    "conto": conto_sel,
                    "valuta": "EUR",
                }
            )

        # Auto-categorizzazione in base al mapping corrente (Req 6.2, 6.4). Si
        # carica il Mapping_Esercente_Categoria (risolto a nomi) e si esegue
        # `categorizza` su ogni transazione: le descrizioni il cui esercente
        # normalizzato è mappato ricevono Categoria/Sotto_Categoria di default,
        # le altre restano da categorizzare. I campi categoria/sotto_categoria/
        # esercente_normalizzato/da_categorizzare vengono riportati sui record.
        mapping_esercente = _carica_mapping_esercente()
        transazioni_dict = [
            categorizza(t, mapping_esercente) for t in transazioni_dict
        ]

        # Mappe nome->id per risolvere la categoria/sotto-categoria assegnata
        # dall'auto-categorizzatore in id da persistere nei record movimento.
        categorie_all = database.get_categorie() or []
        sotto_categorie_all = database.get_sotto_categorie() or []
        categoria_id_by_nome = {
            c.get("nome"): c.get("id")
            for c in categorie_all
            if isinstance(c, dict)
        }
        sotto_id_by_nome_cat = {
            (s.get("nome"), s.get("categoria_id")): s.get("id")
            for s in sotto_categorie_all
            if isinstance(s, dict)
        }
        n_categorizzate = sum(
            1 for t in transazioni_dict if not t.get("da_categorizzare")
        )

        col_cat_auto, col_cat_manuale = st.columns(2)
        col_cat_auto.metric("Auto-categorizzate", n_categorizzate)
        col_cat_manuale.metric(
            "Da categorizzare", len(transazioni_dict) - n_categorizzate
        )

        # Anteprima tabellare dei movimenti importabili.
        with st.expander(f"Anteprima movimenti importabili ({len(importabili)})", expanded=True):
            try:
                import pandas as pd

                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Data": r["data_movimento"],
                                "Descrizione": r["descrizione"],
                                "Importo (€)": r["importo_eur"],
                                "Tipo": r["tipo_movimento"],
                                "Categoria": r.get("categoria") or "(da categorizzare)",
                                "Sotto-categoria": r.get("sotto_categoria") or "",
                            }
                            for r in transazioni_dict
                        ]
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
            except Exception:  # fallback difensivo se pandas non è disponibile
                for r in transazioni_dict:
                    st.write(
                        f"- {r['data_movimento']} · {r['descrizione']} · "
                        f"{r['importo_eur']:.2f} € · {r['tipo_movimento']}"
                    )

        # Proposta delle coppie di Trasferimento (Req 7.4): richiede sia i
        # movimenti già presenti sul conto sia quelli in arrivo, così da
        # individuare uscite/entrate speculari tra conti diversi.
        movimenti_esistenti = database.get_movimenti() or []
        coppie = rileva_coppie_trasferimento(
            list(movimenti_esistenti) + transazioni_dict
        )
        if coppie:
            with st.expander(
                f"Possibili trasferimenti rilevati ({len(coppie)})"
            ):
                st.caption(
                    "Coppie uscita/entrata speculari tra conti diversi. Potrai "
                    "riclassificarle come Trasferimento dal tab «Trasferimenti»."
                )
                for uscita, entrata in coppie:
                    st.write(
                        f"- {uscita.get('data_movimento')} · "
                        f"{uscita.get('conto')} → {entrata.get('conto')} · "
                        f"{abs(float(entrata.get('importo_eur', 0))):.2f} €"
                    )

        # Preparazione dei record per l'upsert idempotente (Req 5.3, 5.5):
        # separa validi/scartati in base alla calcolabilità della chiave.
        preparazione = prepara_per_upsert(transazioni_dict, conto_sel)
        validi = preparazione.get("validi", [])
        conteggi = preparazione.get("conteggi", {})
        n_nuovi = conteggi.get("nuovi", 0)
        n_scartati = conteggi.get("scartati", 0) + len(escluse)

        # --- 5) Conferma + upsert idempotente (Req 5.1, 5.5, 5.6, 5.7) -------
        if not st.button("⬆️ Importa movimenti", type="primary", key="pdf_importa"):
            return

        conto_id = conto_id_by_nome.get(conto_sel)
        if conto_id is None:
            st.error(
                "❌ Impossibile risolvere il conto selezionato. Import annullato."
            )
            return

        # Costruzione dei record definitivi per la tabella movimenti: la
        # chiave naturale usa conto_id, importo_eur e descrizione_normalizzata.
        records = []
        for v in validi:
            # Risoluzione della categoria auto-assegnata (Req 6.2): se
            # `categorizza` ha valorizzato la categoria dal mapping, la si
            # traduce in categoria_id/sotto_categoria_id per il record.
            categoria_nome = v.get("categoria")
            categoria_id = categoria_id_by_nome.get(categoria_nome)
            sotto_nome = v.get("sotto_categoria")
            sotto_categoria_id = (
                sotto_id_by_nome_cat.get((sotto_nome, categoria_id))
                if sotto_nome is not None
                else None
            )
            records.append(
                {
                    "data_movimento": v.get("data_movimento"),
                    "conto_id": conto_id,
                    "importo_eur": v.get("importo_eur"),
                    "tipo_movimento": v.get("tipo_movimento", "Spese"),
                    "valuta": v.get("valuta", "EUR"),
                    "descrizione": v.get("descrizione"),
                    "descrizione_normalizzata": v.get("descrizione_normalizzata"),
                    "categoria_id": categoria_id,
                    "sotto_categoria_id": sotto_categoria_id,
                }
            )

        if not records:
            st.warning("Nessun movimento valido da importare.")
            return

        with st.spinner("Salvataggio movimenti in corso…"):
            esito = database.upsert_movimenti(records)

        if esito is None:
            # Req 5.6: fallimento del salvataggio -> rollback, stato precedente
            # preservato (l'upsert batch è atomico lato Supabase).
            st.error(
                "❌ Salvataggio non riuscito: le modifiche sono state annullate "
                "e lo stato dei movimenti precedente alla riconciliazione è "
                "stato preservato."
            )
            return

        # Req 5.7: saldo del conto ricalcolato dai movimenti aggiornati.
        movimenti_conto = database.get_movimenti(conto=conto_sel) or []
        saldo = saldo_conto(movimenti_conto)

        # Req 5.5 + 9.4: conteggi dell'esito (0 per le categorie vuote).
        st.success("✅ Import completato.")
        c_nuovi, c_scartati, c_saldo = st.columns(3)
        c_nuovi.metric("Movimenti elaborati", n_nuovi)
        c_scartati.metric("Scartati", n_scartati)
        c_saldo.metric(f"Saldo «{conto_sel}»", f"{saldo:,.2f} €")

    except Exception as e:  # difensivo: non far crashare la UI (Req 9.5)
        logger.error(
            "Errore durante l'import dell'estratto conto PDF: %s", e, exc_info=True
        )
        st.error(
            "Si è verificato un errore durante l'import dell'estratto conto. "
            "Nessun dato è stato modificato."
        )


def _tab_trasferimenti() -> None:
    """Tab Trasferimenti: registrazione/riclassificazione coppie (Req 7).

    Due sezioni complementari:

    1. **Nuovo trasferimento**: un form con i selectbox del Conto di origine e
       del Conto di destinazione, l'importo e la data valuta. La validazione
       (Req 7.3) rifiuta la registrazione, senza creare alcun Movimento, se il
       Conto di origine coincide con quello di destinazione o se l'importo non
       è strettamente positivo. Alla conferma valida si chiama
       `database.insert_trasferimento`, che inserisce i due Movimenti speculari
       ("Trasferimento uscita"/"Trasferimento ingresso") in modo atomico per
       compensazione (Req 7.1, 7.2): su successo si mostra una conferma
       (Req 9.4), su esito `None` un messaggio di errore/rollback.

    2. **Lato mancante di un trasferimento esistente** (Req 7.6): quando esiste
       un solo lato di un Trasferimento (es. è stata registrata la sola uscita
       senza l'entrata speculare, o viceversa) si può proporre la coppia e
       inserire il lato speculare mancante. L'inserimento del solo lato
       mancante riusa `database.insert_trasferimento` creando entrambi i lati e
       riclassificando così la coppia come Trasferimento completo.

    L'intero corpo è protetto da try/except per non far crashare la UI (Req 9.5).
    """
    st.subheader("Trasferimenti tra conti")

    try:
        conti = database.get_conti() or []
        nomi_conti = sorted(
            {c.get("nome") for c in conti if isinstance(c, dict) and c.get("nome")}
        )
        conto_id_by_nome = {
            c.get("nome"): c.get("id") for c in conti if isinstance(c, dict)
        }

        if len(nomi_conti) < 2:
            st.warning(
                "Servono almeno due conti per registrare un trasferimento. "
                "Crea i conti (es. tramite l'import dello storico Excel) e "
                "riprova."
            )
            return

        # --- 1) Nuovo trasferimento -----------------------------------------
        st.markdown("### Nuovo trasferimento")
        with st.form("form_nuovo_trasferimento"):
            col_orig, col_dest = st.columns(2)
            with col_orig:
                conto_origine = st.selectbox(
                    "Conto di origine",
                    options=nomi_conti,
                    index=0,
                    key="trasf_origine",
                )
            with col_dest:
                conto_dest = st.selectbox(
                    "Conto di destinazione",
                    options=nomi_conti,
                    index=1 if len(nomi_conti) > 1 else 0,
                    key="trasf_dest",
                )

            col_imp, col_data = st.columns(2)
            with col_imp:
                importo = st.number_input(
                    "Importo (€)",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="trasf_importo",
                )
            with col_data:
                data_trasf = st.date_input(
                    "Data valuta",
                    value=date.today(),
                    key="trasf_data",
                )

            nota = st.text_input("Nota (facoltativa)", key="trasf_nota")

            inviato = st.form_submit_button("💸 Registra trasferimento", type="primary")

        if inviato:
            _registra_trasferimento(
                conto_origine=conto_origine,
                conto_dest=conto_dest,
                importo=importo,
                data_trasf=data_trasf,
                nota=nota,
                conto_id_by_nome=conto_id_by_nome,
            )

        st.divider()

        # --- 2) Lato mancante di un trasferimento esistente (Req 7.6) --------
        st.markdown("### Completa un trasferimento a lato singolo")
        st.caption(
            "Movimenti che sembrano un lato isolato di un trasferimento "
            "(un'uscita o un'entrata senza il lato speculare). Puoi inserire il "
            "lato mancante per completarli."
        )

        _sezione_lato_mancante(conti, conto_id_by_nome)

    except Exception as e:  # difensivo: non far crashare la UI (Req 9.5)
        logger.error("Errore nel tab Trasferimenti: %s", e, exc_info=True)
        st.error(
            "Si è verificato un errore nel tab Trasferimenti. "
            "Nessun dato è stato modificato."
        )


def _registra_trasferimento(
    conto_origine: str,
    conto_dest: str,
    importo: float,
    data_trasf,
    nota: str,
    conto_id_by_nome: dict,
) -> None:
    """Valida e registra un nuovo trasferimento (Req 7.1, 7.2, 7.3, 9.4).

    Applica la validazione del Req 7.3 (conti diversi e importo > 0): se non
    supera i controlli mostra un messaggio di errore e NON crea alcun Movimento.
    Altrimenti chiama `database.insert_trasferimento` e interpreta l'esito.
    """
    # Req 7.3: conto origine != destinazione.
    if conto_origine == conto_dest:
        st.error(
            "❌ Il conto di origine e quello di destinazione devono essere "
            "diversi. Nessun movimento è stato creato."
        )
        return

    # Req 7.3: importo strettamente positivo.
    importo_valido, importo_val = _valida_importo(importo)
    if not importo_valido or importo_val is None or importo_val <= 0:
        st.error(
            "❌ L'importo del trasferimento deve essere maggiore di zero. "
            "Nessun movimento è stato creato."
        )
        return

    conto_origine_id = conto_id_by_nome.get(conto_origine)
    conto_dest_id = conto_id_by_nome.get(conto_dest)
    if conto_origine_id is None or conto_dest_id is None:
        st.error(
            "❌ Impossibile risolvere i conti selezionati. Trasferimento "
            "annullato."
        )
        return

    data_iso = _to_iso(data_trasf)
    if data_iso is None:
        st.error("❌ Data del trasferimento non valida. Trasferimento annullato.")
        return

    nota_pulita = (nota or "").strip() or None

    try:
        esito = database.insert_trasferimento(
            conto_origine_id, conto_dest_id, importo_val, data_iso, nota_pulita
        )
    except Exception as e:  # difensivo (Req 9.5)
        logger.error("Errore insert_trasferimento: %s", e, exc_info=True)
        esito = None

    if esito is None:
        # Req 7.2: fallimento con rollback per compensazione del primo lato.
        st.error(
            "❌ Registrazione del trasferimento non riuscita: eventuali "
            "movimenti parziali sono stati annullati e i saldi dei conti non "
            "sono stati alterati."
        )
        return

    # Req 7.1 + 9.4: conferma dell'operazione.
    st.success(
        f"✅ Trasferimento di {importo_val:,.2f} € registrato da "
        f"«{conto_origine}» a «{conto_dest}» ({data_iso})."
    )


def _sezione_lato_mancante(conti: list, conto_id_by_nome: dict) -> None:
    """Propone e completa i trasferimenti registrati con un solo lato (Req 7.6).

    Individua i Movimenti di tipo "Trasferimento uscita"/"Trasferimento
    ingresso" privi del lato speculare (stessa data e importo assoluto, conto
    diverso, tipo opposto). Per ciascun lato isolato offre un form per
    selezionare il conto dell'altro lato e inserire il Movimento mancante,
    riusando `database.insert_trasferimento` per creare la coppia completa.
    """
    nome_by_id = {
        c.get("id"): c.get("nome") for c in conti if isinstance(c, dict)
    }
    nomi_conti = sorted(v for v in nome_by_id.values() if v)

    try:
        movimenti = database.get_movimenti() or []
    except Exception as e:  # difensivo (Req 9.5)
        logger.error("Errore get_movimenti nel tab Trasferimenti: %s", e)
        movimenti = []

    lati_isolati = _trova_lati_trasferimento_isolati(movimenti)

    if not lati_isolati:
        st.info("Nessun trasferimento a lato singolo rilevato.")
        return

    for idx, mov in enumerate(lati_isolati):
        mid = mov.get("id")
        tipo = mov.get("tipo_movimento")
        conto_nome = nome_by_id.get(mov.get("conto_id")) or "(sconosciuto)"
        data_iso = _to_iso(mov.get("data_movimento"))
        importo = _valida_importo(mov.get("importo_eur"))[1] or 0.0
        verso = "uscita" if tipo == "Trasferimento uscita" else "ingresso"
        etichetta_altro = (
            "Conto di destinazione (ingresso)"
            if verso == "uscita"
            else "Conto di origine (uscita)"
        )

        with st.expander(
            f"{data_iso or '—'} · «{conto_nome}» · {abs(importo):,.2f} € · "
            f"lato {verso} (ID {mid})"
        ):
            altri_conti = [n for n in nomi_conti if n != conto_nome] or nomi_conti
            with st.form(f"form_lato_mancante_{mid}_{idx}"):
                altro_conto = st.selectbox(
                    etichetta_altro,
                    options=altri_conti,
                    key=f"lato_altro_conto_{mid}_{idx}",
                )
                inviato = st.form_submit_button("➕ Inserisci lato mancante")

            if not inviato:
                continue

            _completa_lato_mancante(
                mov=mov,
                verso=verso,
                conto_corrente_nome=conto_nome,
                altro_conto_nome=altro_conto,
                importo=importo,
                data_iso=data_iso,
                conto_id_by_nome=conto_id_by_nome,
            )


def _trova_lati_trasferimento_isolati(movimenti: list) -> list:
    """Ritorna i movimenti di Trasferimento privi del lato speculare (Req 7.6).

    Un lato "uscita" è isolato se non esiste un "Trasferimento ingresso" su un
    conto diverso con stessa data e stesso importo assoluto (e viceversa). Il
    confronto sull'importo usa l'arrotondamento a 2 decimali per tollerare la
    rappresentazione in virgola mobile.
    """
    uscite = []
    ingressi = []
    for m in movimenti:
        if not isinstance(m, dict):
            continue
        tipo = m.get("tipo_movimento")
        if tipo == "Trasferimento uscita":
            uscite.append(m)
        elif tipo == "Trasferimento ingresso":
            ingressi.append(m)

    def _firma(mov):
        data = _to_iso(mov.get("data_movimento")) or ""
        importo = _valida_importo(mov.get("importo_eur"))[1]
        importo_key = round(abs(importo), 2) if importo is not None else None
        return data, importo_key, mov.get("conto_id")

    firme_ingressi = [_firma(m) for m in ingressi]
    firme_uscite = [_firma(m) for m in uscite]

    def _ha_speculare(firma, controparti):
        data, importo_key, conto_id = firma
        if importo_key is None:
            return False
        for d, imp, cid in controparti:
            if d == data and imp == importo_key and cid != conto_id:
                return True
        return False

    isolati = []
    for m, firma in zip(uscite, firme_uscite):
        if not _ha_speculare(firma, firme_ingressi):
            isolati.append(m)
    for m, firma in zip(ingressi, firme_ingressi):
        if not _ha_speculare(firma, firme_uscite):
            isolati.append(m)
    return isolati


def _completa_lato_mancante(
    mov: dict,
    verso: str,
    conto_corrente_nome: str,
    altro_conto_nome: str,
    importo: float,
    data_iso,
    conto_id_by_nome: dict,
) -> None:
    """Inserisce il lato mancante di un trasferimento a lato singolo (Req 7.6).

    `verso` indica il lato già esistente: "uscita" significa che manca il lato
    ingresso (il conto corrente è l'origine, `altro_conto_nome` la
    destinazione); "ingresso" significa che manca il lato uscita (il conto
    corrente è la destinazione, `altro_conto_nome` l'origine).
    """
    importo_abs = abs(importo)
    if importo_abs <= 0:
        st.error("❌ Importo del movimento non valido. Nessun lato inserito.")
        return

    if altro_conto_nome == conto_corrente_nome:
        st.error(
            "❌ Il conto dell'altro lato deve essere diverso. Nessun lato "
            "inserito."
        )
        return

    if verso == "uscita":
        origine_nome, dest_nome = conto_corrente_nome, altro_conto_nome
    else:
        origine_nome, dest_nome = altro_conto_nome, conto_corrente_nome

    origine_id = conto_id_by_nome.get(origine_nome)
    dest_id = conto_id_by_nome.get(dest_nome)
    data_val = _to_iso(data_iso)
    if origine_id is None or dest_id is None or data_val is None:
        st.error(
            "❌ Impossibile risolvere i conti o la data. Nessun lato inserito."
        )
        return

    nota = (mov.get("nota") or "").strip() or None

    try:
        esito = database.insert_trasferimento(
            origine_id, dest_id, importo_abs, data_val, nota
        )
    except Exception as e:  # difensivo (Req 9.5)
        logger.error("Errore insert_trasferimento (lato mancante): %s", e)
        esito = None

    if esito is None:
        st.error(
            "❌ Inserimento del lato mancante non riuscito: eventuali movimenti "
            "parziali sono stati annullati."
        )
        return

    st.success(
        f"✅ Lato mancante inserito: trasferimento di {importo_abs:,.2f} € tra "
        f"«{origine_nome}» e «{dest_nome}» completato ({data_val})."
    )
    st.rerun()


def _to_iso(valore):
    """Converte un valore date/datetime/ISO in stringa ISO YYYY-MM-DD o None."""
    convertita = _to_date(valore)
    if convertita is None:
        return None
    return convertita.isoformat()


def _tab_saldi() -> None:
    """Tab Saldi: saldo per conto (Req 5.7).

    Recupera tutti i Movimenti (via `database.get_movimenti`), li raggruppa per
    `conto_id` e calcola per ciascun Conto il saldo con
    `spese.riconciliatore.saldo_conto` (somma algebrica con segno degli importi
    dei movimenti del conto, Req 5.7). Mostra una riga per Conto con il saldo e,
    per comodità, un saldo complessivo.

    Tutte le interazioni con il DB sono difensive: in caso di errore si mostra
    un messaggio e non si fa crashare la UI (Req 9.5).
    """
    st.subheader("Saldi per conto")

    try:
        conti = database.get_conti() or []
        nome_by_id = {
            c.get("id"): c.get("nome")
            for c in conti
            if isinstance(c, dict) and c.get("id") is not None
        }

        try:
            movimenti = database.get_movimenti() or []
        except Exception as e:  # difensivo (Req 9.5)
            logger.error("Errore get_movimenti nel tab Saldi: %s", e)
            movimenti = []

        if not conti and not movimenti:
            st.info("Nessun conto o movimento presente.")
            return

        # Raggruppamento dei movimenti per conto_id.
        movimenti_per_conto: dict = {}
        for m in movimenti:
            if not isinstance(m, dict):
                continue
            cid = m.get("conto_id")
            movimenti_per_conto.setdefault(cid, []).append(m)

        # Includiamo anche i conti senza movimenti (saldo 0), oltre a eventuali
        # conto_id presenti nei movimenti ma non più nell'elenco conti.
        tutti_i_conti_id = set(nome_by_id.keys()) | set(movimenti_per_conto.keys())

        righe = []
        saldo_totale = 0.0
        for cid in tutti_i_conti_id:
            movimenti_conto = movimenti_per_conto.get(cid, [])
            saldo = saldo_conto(movimenti_conto)
            saldo_totale += saldo
            nome = nome_by_id.get(cid) or f"(conto {cid})"
            righe.append({"Conto": nome, "Saldo (€)": round(saldo, 2)})

        if not righe:
            st.info("Nessun conto o movimento presente.")
            return

        righe.sort(key=lambda r: r["Conto"])

        try:
            import pandas as pd

            st.dataframe(
                pd.DataFrame(righe),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Saldo (€)": st.column_config.NumberColumn(
                        "Saldo (€)", format="%.2f"
                    )
                },
            )
        except Exception:  # fallback difensivo se pandas non è disponibile
            for r in righe:
                st.write(f"- {r['Conto']}: {r['Saldo (€)']:,.2f} €")

        st.metric("Saldo complessivo", f"{saldo_totale:,.2f} €")

    except Exception as e:  # difensivo: non far crashare la UI (Req 9.5)
        logger.error("Errore nel tab Saldi: %s", e, exc_info=True)
        st.error(
            "Si è verificato un errore nel tab Saldi. "
            "I saldi non sono stati calcolati."
        )

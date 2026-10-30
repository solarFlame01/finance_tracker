"""Riconciliazione e deduplicazione dei movimenti, helper su saldo/filtri/trasferimenti.

Modulo di dominio puro. Altre funzioni (`rileva_coppie_trasferimento`,
`prepara_per_upsert`, helper di visualizzazione) saranno aggiunte in altri
task. Qui e' implementato `saldo_conto`.
"""

from __future__ import annotations

from typing import Any

from spese.normalizza import chiave_naturale_movimento


def saldo_conto(movimenti_conto: list[dict]) -> float:
    """Calcola il saldo di un conto come somma algebrica con segno degli importi.

    Il saldo e' la somma di `importo_eur` di tutti i movimenti del conto, dove
    il segno e' gia' incorporato nel valore di `importo_eur` di ciascun movimento
    (Req 5.7). I movimenti privi di un `importo_eur` numerico valido (None, NaN,
    stringhe non convertibili) sono ignorati senza interrompere il calcolo.

    Args:
        movimenti_conto: lista di movimenti (dict) appartenenti a un singolo conto.

    Returns:
        La somma algebrica degli importi come float. Lista vuota -> 0.0.
    """
    totale = 0.0
    for movimento in movimenti_conto or []:
        if not isinstance(movimento, dict):
            continue
        importo = _importo_numerico(movimento.get("importo_eur"))
        if importo is not None:
            totale += importo
    return totale


def _importo_numerico(valore: Any) -> float | None:
    """Converte un importo in float se possibile, altrimenti None.

    Scarta None, NaN e valori non convertibili per evitare di propagare
    errori o NaN nel saldo complessivo.
    """
    if valore is None:
        return None
    try:
        importo = float(valore)
    except (TypeError, ValueError):
        return None
    if importo != importo:  # NaN check senza dipendere da math
        return None
    return importo

# Tipi di movimento che rappresentano i due lati di un Trasferimento.
# Centralizzati qui per garantire coerenza in ogni visualizzazione (Req 7.5).
TIPI_TRASFERIMENTO: frozenset[str] = frozenset(
    {"Trasferimento ingresso", "Trasferimento uscita"}
)


def e_trasferimento(movimento: dict) -> bool:
    """True se il movimento e' un lato di un Trasferimento.

    Un movimento e' considerato trasferimento quando il suo `tipo_movimento`
    appartiene a `TIPI_TRASFERIMENTO` (`'Trasferimento ingresso'` o
    `'Trasferimento uscita'`). Questo e' il predicato centrale usato per
    escludere i trasferimenti dai totali di spesa/entrata (Req 7.5).
    """
    if not isinstance(movimento, dict):
        return False
    return movimento.get("tipo_movimento") in TIPI_TRASFERIMENTO


def escludi_trasferimenti(movimenti: list[dict]) -> list[dict]:
    """Rimuove i movimenti di tipo Trasferimento da una lista di movimenti.

    Helper di dominio centralizzata (Req 7.5): tutte le aggregazioni di
    spesa/entrata devono filtrare via i movimenti con `tipo_movimento` in
    (`'Trasferimento ingresso'`, `'Trasferimento uscita'`), così che i totali
    restino corretti. L'ordine relativo dei movimenti rimanenti e' preservato.

    Args:
        movimenti: lista di movimenti (dict).

    Returns:
        Una nuova lista contenente solo i movimenti che non sono trasferimenti.
    """
    return [
        movimento
        for movimento in movimenti or []
        if isinstance(movimento, dict) and not e_trasferimento(movimento)
    ]


def _chiave_data(movimento: dict) -> str:
    """Estrae la data del movimento come stringa confrontabile per l'ordinamento.

    Le date ISO (`YYYY-MM-DD`) si ordinano correttamente in ordine
    lessicografico. I movimenti privi di `data_movimento` ricevono una stringa
    vuota, finendo in coda nell'ordinamento decrescente senza interromperlo.
    """
    valore = movimento.get("data_movimento") if isinstance(movimento, dict) else None
    if valore is None:
        return ""
    return str(valore)


def ordina_per_data_desc(movimenti: list[dict]) -> list[dict]:
    """Ordina i movimenti per data in ordine decrescente (non crescente).

    Produce l'elenco così come deve essere mostrato nella visualizzazione
    (Req 8.1). L'ordinamento e' stabile: movimenti con la stessa data
    mantengono l'ordine relativo di ingresso. La lista originale non e'
    modificata.

    Args:
        movimenti: lista di movimenti (dict) con chiave `data_movimento`.

    Returns:
        Una nuova lista ordinata per `data_movimento` dal più recente al più
        vecchio.
    """
    return sorted(movimenti or [], key=_chiave_data, reverse=True)


def applica_filtri(
    movimenti: list[dict],
    conto: str | None = None,
    categoria: str | None = None,
    data_da: str | None = None,
    data_a: str | None = None,
) -> list[dict]:
    """Applica i filtri dell'elenco movimenti (conto, categoria, intervallo date).

    Restituisce esattamente i movimenti che soddisfano tutti i filtri attivi
    (Req 8.3, 8.4, 8.5): nessun movimento conforme viene omesso e nessun
    movimento non conforme viene incluso. Un filtro con valore `None` e'
    considerato inattivo e non restringe i risultati.

    - `conto`: se valorizzato, mantiene solo i movimenti del conto indicato
      (confronto sul campo `conto`).
    - `categoria`: se valorizzata, mantiene solo i movimenti della categoria
      indicata (confronto sul campo `categoria`).
    - `data_da` / `data_a`: intervallo di date con estremi inclusi, confrontato
      sul campo `data_movimento`. Le date sono attese in formato ISO
      (`YYYY-MM-DD`), confrontabili lessicograficamente. Un estremo `None`
      lascia il relativo lato dell'intervallo illimitato.

    Nota: questa funzione non valida l'intervallo (data_da > data_a); la
    validazione dell'intervallo invertito (Req 8.7) e' responsabilità del
    livello UI, che deve rifiutare il filtro senza invocare questa helper.
    L'ordine relativo dei movimenti e' preservato; la lista originale non e'
    modificata.

    Args:
        movimenti: lista di movimenti (dict).
        conto: nome del conto da filtrare, oppure None.
        categoria: nome della categoria da filtrare, oppure None.
        data_da: data iniziale inclusiva (ISO), oppure None.
        data_a: data finale inclusiva (ISO), oppure None.

    Returns:
        Una nuova lista con i soli movimenti che soddisfano tutti i filtri.
    """
    risultato: list[dict] = []
    for movimento in movimenti or []:
        if not isinstance(movimento, dict):
            continue
        if conto is not None and movimento.get("conto") != conto:
            continue
        if categoria is not None and movimento.get("categoria") != categoria:
            continue
        if data_da is not None or data_a is not None:
            data_movimento = _chiave_data(movimento)
            if data_da is not None and data_movimento < str(data_da):
                continue
            if data_a is not None and data_movimento > str(data_a):
                continue
        risultato.append(movimento)
    return risultato


# Tipi di movimento che rappresentano, rispettivamente, un'uscita e un'entrata
# "grezze" (pre-riclassificazione) candidabili a formare una coppia di
# Trasferimento. Il Parser_PDF assegna "Spese" alle uscite e "In" alle entrate
# (Req 4.7); i movimenti già marcati come Trasferimento non sono candidati.
TIPO_USCITA: str = "Spese"
TIPO_ENTRATA: str = "In"


def rileva_coppie_trasferimento(
    movimenti: list[dict],
) -> list[tuple[dict, dict]]:
    """Individua le coppie (uscita conto A, entrata conto B!=A) che sembrano un Trasferimento.

    Una coppia e' composta da un movimento di uscita da un conto e da un
    movimento di entrata in un conto **diverso**, con differenza di importo
    pari a 0 e differenza di data pari a 0 giorni (Req 7.4). Tali coppie sono
    proposte all'Utente per la riclassificazione come Trasferimento; questa
    funzione non modifica i movimenti, si limita a individuarle.

    Criteri (tutti necessari) per considerare uscita `u` ed entrata `e` una coppia:
    - `u` e' un'uscita (`tipo_movimento == 'Spese'`) ed `e` e' un'entrata
      (`tipo_movimento == 'In'`); i movimenti già di tipo Trasferimento, o di
      altri tipi, non sono candidati;
    - i conti sono valorizzati e diversi (`u['conto'] != e['conto']`);
    - stessa data (`u['data_movimento'] == e['data_movimento']`, confronto sul
      valore normalizzato a stringa, coerente con le date ISO del dominio);
    - differenza di importo pari a 0, cioè le due grandezze si compensano:
      l'uscita ha importo negativo e l'entrata positivo, quindi
      `abs(u_importo) == abs(e_importo)`. I movimenti con importo non numerico
      (None, NaN, non convertibile) non possono formare coppia e sono ignorati.

    L'importo e' confrontato in valore assoluto arrotondato a 2 decimali per
    tollerare la rappresentazione in virgola mobile senza alterare la semantica
    "differenza = 0" sugli importi monetari.

    Ogni movimento puo' comparire in più coppie se più candidati soddisfano i
    criteri (es. due entrate speculari sullo stesso conto opposto): la funzione
    non decide l'abbinamento univoco, che resta scelta dell'Utente in fase di
    riclassificazione. L'ordine delle coppie segue l'ordine delle uscite e, a
    parità di uscita, l'ordine delle entrate nella lista in ingresso. La lista
    originale e i movimenti non sono modificati.

    Args:
        movimenti: lista di movimenti (dict) con chiavi `tipo_movimento`,
            `conto`, `data_movimento`, `importo_eur`.

    Returns:
        Lista di tuple `(uscita, entrata)`. Lista vuota se nessuna coppia
        soddisfa i criteri.
    """
    candidati = [m for m in movimenti or [] if isinstance(m, dict)]

    uscite: list[tuple[dict, str, str, float]] = []
    entrate: list[tuple[dict, str, str, float]] = []
    for movimento in candidati:
        importo = _importo_numerico(movimento.get("importo_eur"))
        if importo is None:
            continue
        conto = movimento.get("conto")
        if conto is None or str(conto) == "":
            continue
        data = _chiave_data(movimento)
        if data == "":
            continue
        tipo = movimento.get("tipo_movimento")
        chiave = round(abs(importo), 2)
        if tipo == TIPO_USCITA:
            uscite.append((movimento, str(conto), data, chiave))
        elif tipo == TIPO_ENTRATA:
            entrate.append((movimento, str(conto), data, chiave))

    coppie: list[tuple[dict, dict]] = []
    for mov_uscita, conto_uscita, data_uscita, importo_uscita in uscite:
        for mov_entrata, conto_entrata, data_entrata, importo_entrata in entrate:
            if conto_uscita == conto_entrata:
                continue
            if data_uscita != data_entrata:
                continue
            if importo_uscita != importo_entrata:
                continue
            coppie.append((mov_uscita, mov_entrata))
    return coppie


def prepara_per_upsert(transazioni: list[dict], conto: str) -> dict:
    """Prepara le transazioni di un estratto conto per l'upsert idempotente.

    Funzione di dominio PURA: non legge né scrive su DB. Per ogni transazione
    calcola la Chiave_Naturale_Movimento tramite
    `chiave_naturale_movimento(data_movimento, conto, importo_eur, descrizione)`
    e separa le transazioni in due gruppi (Req 5.3, 5.5):

    - `validi`: transazioni per cui la chiave naturale è calcolabile. Ogni
      record restituito è una copia della transazione a cui vengono aggiunti il
      `conto` passato in input, la `descrizione_normalizzata` (quarto elemento
      della chiave) e la tupla `chiave_naturale`, pronto per essere passato alla
      funzione di upsert del layer dati.
    - `scartati`: transazioni per cui la chiave naturale NON è calcolabile
      (`chiave_naturale_movimento` restituisce `None`), perché manca o non è
      valido un componente obbligatorio (data, conto, importo o descrizione,
      Req 5.3). I record scartati sono restituiti come copie non modificate.

    I conteggi sono SEMPRE presenti e valorizzati a 0 per le categorie prive di
    movimenti (Req 5.5): `nuovi` (numero di validi pronti per l'upsert) e
    `scartati` (numero di transazioni senza chiave calcolabile). Il conteggio
    dei movimenti già presenti e ignorati (`gia_presenti`) dipende dall'esito
    dell'upsert idempotente lato DB e non è determinabile da questa funzione
    pura; viene quindi inizializzato a 0 e resta a 0 finché il layer dati non lo
    aggiorna dopo il salvataggio.

    La data del movimento è letta dalla chiave canonica `data_movimento`; per
    robustezza verso transazioni di provenienza grezza (es. parser PDF) è
    accettata anche la chiave `data` come ripiego. L'importo è letto da
    `importo_eur` e la descrizione da `descrizione`, coerentemente con le altre
    helper di dominio. Il `conto` usato per la chiave è SEMPRE quello passato
    come argomento, non quello eventualmente presente nella transazione, perché
    il Conto è selezionato dall'Utente al momento dell'import (Req 4.3).

    L'ordine relativo delle transazioni è preservato all'interno di ciascun
    gruppo; le transazioni di input non vengono mutate (si restituiscono copie).

    Args:
        transazioni: lista di transazioni (dict) estratte/categorizzate, con
            chiavi `data_movimento` (o `data`), `importo_eur` e `descrizione`.
        conto: nome del Conto selezionato dall'Utente a cui associare i
            movimenti e usato per calcolare la chiave naturale.

    Returns:
        Un dizionario con:
        - `validi`: lista dei record pronti per l'upsert (con `conto`,
          `descrizione_normalizzata` e `chiave_naturale`);
        - `scartati`: lista delle transazioni scartate (copie non modificate);
        - `conteggi`: dizionario `{"nuovi": int, "gia_presenti": int,
          "scartati": int}` con valori sempre presenti (0 per i gruppi vuoti).
    """
    validi: list[dict] = []
    scartati: list[dict] = []

    for transazione in transazioni or []:
        if not isinstance(transazione, dict):
            continue

        data = transazione.get("data_movimento")
        if data is None:
            data = transazione.get("data")
        importo = transazione.get("importo_eur")
        descrizione = transazione.get("descrizione")

        chiave = chiave_naturale_movimento(data, conto, importo, descrizione)

        if chiave is None:
            # Chiave naturale non calcolabile -> scarto (Req 5.3).
            scartati.append(dict(transazione))
            continue

        record = dict(transazione)
        record["conto"] = conto
        record["descrizione_normalizzata"] = chiave[3]
        record["chiave_naturale"] = chiave
        validi.append(record)

    return {
        "validi": validi,
        "scartati": scartati,
        "conteggi": {
            "nuovi": len(validi),
            "gia_presenti": 0,
            "scartati": len(scartati),
        },
    }

"""Auto-categorizzazione dei movimenti basata sul mapping esercente -> categoria.

Modulo di dominio puro, indipendente da Streamlit e Supabase.

- `categorizza`: assegna Categoria/Sotto_Categoria a un movimento in base al
  Mapping_Esercente_Categoria, usando `normalize_esercente` per ricavare la
  chiave dell'esercente dalla descrizione (Req 6.2, 6.3, 6.4, 6.7, 6.8).
- `aggiorna_mapping_da_correzione`: costruisce il record di mapping da
  persistere via upsert quando l'utente crea/corregge manualmente la categoria
  di un movimento (Req 6.5, 6.6).
"""

from spese.normalizza import normalize_esercente


def categorizza(movimento: dict, mapping: dict[str, dict]) -> dict:
    """Assegna Categoria/Sotto_Categoria a un movimento in base al mapping.

    Funzione PURA: non legge né scrive su DB. Calcola l'esercente normalizzato
    dalla descrizione del movimento tramite `normalize_esercente` e lo cerca nel
    `mapping` passato in input (riflette l'ultima correzione manuale, Req 6.7).

    Comportamento (Req 6.2, 6.3, 6.4):

    - Se l'esercente normalizzato è presente nel `mapping`, assegna al movimento
      la `categoria` della voce corrispondente e, se la voce contiene anche una
      `sotto_categoria`, la assegna; il flag `da_categorizzare` è `False`.
    - Altrimenti lascia la `categoria` a `None`, la `sotto_categoria` a `None` e
      imposta `da_categorizzare=True`.

    Il movimento di input non viene mutato: viene restituita una copia con i
    campi aggiornati.

    Args:
        movimento: Dizionario del movimento. La descrizione grezza è letta dalla
            chiave ``"descrizione"`` (assente/``None`` -> esercente vuoto).
        mapping: Dizionario esercente_normalizzato -> voce di mapping. Ogni voce
            è un dizionario che espone almeno la chiave ``"categoria"`` e,
            opzionalmente, ``"sotto_categoria"``.

    Returns:
        Una copia del movimento con i campi ``"esercente_normalizzato"``,
        ``"categoria"``, ``"sotto_categoria"`` e ``"da_categorizzare"``
        valorizzati secondo le regole sopra.
    """
    risultato = dict(movimento)

    esercente_norm = normalize_esercente(movimento.get("descrizione"))
    risultato["esercente_normalizzato"] = esercente_norm

    voce = mapping.get(esercente_norm) if esercente_norm else None

    if voce is not None:
        risultato["categoria"] = voce.get("categoria")
        risultato["sotto_categoria"] = voce.get("sotto_categoria")
        risultato["da_categorizzare"] = False
    else:
        risultato["categoria"] = None
        risultato["sotto_categoria"] = None
        risultato["da_categorizzare"] = True

    return risultato


def aggiorna_mapping_da_correzione(
    esercente_norm: str,
    categoria: str,
    sotto_categoria: str | None,
) -> dict:
    """Costruisce il record di mapping da persistere via upsert su correzione.

    Funzione PURA: non legge né scrive su DB. Prepara il dizionario che
    rappresenta la voce del Mapping_Esercente_Categoria da inviare all'upsert
    quando l'Utente assegna o corregge manualmente la Categoria di un Movimento
    (Req 6.5, 6.6). L'upsert sull'esercente normalizzato unifica i due casi:

    - se l'esercente non è ancora presente, viene creata una nuova voce
      (Req 6.5);
    - se l'esercente è già presente, la voce esistente viene aggiornata con la
      nuova Categoria e la nuova Sotto_Categoria (Req 6.6).

    L'esercente viene normalizzato di nuovo tramite `normalize_esercente` per
    garantire che la chiave usata in scrittura coincida con quella calcolata in
    fase di lettura/auto-categorizzazione (Req 6.8), rendendo la funzione
    robusta anche se riceve una descrizione grezza invece di una chiave già
    normalizzata.

    Args:
        esercente_norm: Esercente (normalizzato o grezzo) a cui associare la
            categoria. Viene comunque ripassato da `normalize_esercente`.
        categoria: Categoria di default da associare all'esercente.
        sotto_categoria: Sotto_Categoria di default, oppure ``None`` se la
            correzione indica solo la Categoria.

    Returns:
        Dizionario con le chiavi ``"esercente_normalizzato"``, ``"categoria"``
        e ``"sotto_categoria"``, pronto per essere passato alla funzione di
        upsert del mapping.
    """
    return {
        "esercente_normalizzato": normalize_esercente(esercente_norm),
        "categoria": categoria,
        "sotto_categoria": sotto_categoria,
    }

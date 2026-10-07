"""
Script di manutenzione: aggiorna lo storico prezzi (etf_price_history) scaricando
i dati completi da Yahoo Finance per tutti gli ETF presenti nel portafoglio.

Serve per colmare i buchi nello storico (es. mesi recenti mancanti) così che le
viste di rendimento mensile/annuo usino prezzi reali invece del forward-fill.

Uso (dal terminale, con il venv del progetto attivo):

    python aggiorna_storico_prezzi.py
    python aggiorna_storico_prezzi.py SUAS EIMI     # solo alcuni ticker

NOTA: scarica period="max" e fa upsert su etf_price_history (nessuna
cancellazione). yfinance puo' essere lento: c'e' una pausa tra i ticker.
"""
import sys
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
logger = logging.getLogger("aggiorna_storico_prezzi")


def _ticker_in_portafoglio():
    """Ricava i ticker ETF distinti dalle transazioni reali (escludendo i bond M.*)."""
    from database import supabase
    resp = (
        supabase.table("transaction")
        .select("ticker, isin, protocollo")
        .execute()
    )
    tickers = set()
    for row in resp.data or []:
        tk = (row.get("ticker") or "").strip()
        isin = (row.get("isin") or "").strip()
        proto = row.get("protocollo")
        if not tk or tk.startswith("M.") or isin in ("", "0"):
            continue
        try:
            if float(proto) != 0.0:
                continue
        except (TypeError, ValueError):
            continue
        tickers.add(tk)
    return sorted(tickers)


def aggiorna_storico(tickers=None, pausa=3, progress_cb=None):
    """Scarica e fa upsert dello storico prezzi per i ticker indicati.

    Args:
        tickers (list[str] | None): elenco ticker; se None usa quelli in portafoglio.
        pausa (int): secondi di pausa tra un ticker e l'altro (anti-blocco Yahoo).
        progress_cb (callable | None): callback opzionale chiamata come
            progress_cb(indice, totale, ticker, righe) per aggiornare una UI.

    Returns:
        dict: {"ok": int, "ko": int, "totale": int, "dettaglio": list[dict]}
    """
    from finance_info import get_all_etf_history

    if not tickers:
        tickers = _ticker_in_portafoglio()

    risultato = {"ok": 0, "ko": 0, "totale": len(tickers or []), "dettaglio": []}
    if not tickers:
        logger.warning("Nessun ticker da aggiornare.")
        return risultato

    for i, tk in enumerate(tickers, 1):
        logger.info("[%d/%d] Scarico storico per %s ...", i, len(tickers), tk)
        righe = 0
        esito = "ok"
        try:
            df = get_all_etf_history(tk)
            if df is not None and not df.empty:
                righe = len(df)
                logger.info("  -> %s: %d righe (upsert su etf_price_history)", tk, righe)
                risultato["ok"] += 1
            else:
                esito = "vuoto"
                logger.warning("  -> %s: nessun dato ricevuto", tk)
                risultato["ko"] += 1
        except Exception as e:
            esito = f"errore: {e}"
            logger.error("  -> %s: errore %s", tk, e)
            risultato["ko"] += 1

        risultato["dettaglio"].append({"ticker": tk, "righe": righe, "esito": esito})
        if progress_cb is not None:
            try:
                progress_cb(i, len(tickers), tk, righe)
            except Exception:
                pass

        # Pausa per non farsi bloccare da Yahoo
        if pausa and i < len(tickers):
            time.sleep(pausa)

    logger.info("Completato. Successi: %d  Falliti: %d", risultato["ok"], risultato["ko"])
    return risultato


def main(argv):
    tickers = argv[1:] if len(argv) > 1 else None
    if tickers:
        logger.info("Ticker richiesti da riga di comando: %s", ", ".join(tickers))
    else:
        tickers = _ticker_in_portafoglio()
        logger.info("Ticker in portafoglio: %s", ", ".join(tickers))
    aggiorna_storico(tickers)


if __name__ == "__main__":
    main(sys.argv)

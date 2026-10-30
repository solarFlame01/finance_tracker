# Feature: gestione-spese, task 8.7: Unit/edge-case test del parser PDF
"""Test unit/edge-case per il parsing dei PDF (task 8.7).

Coprono due comportamenti di confine del Parser_PDF:

- Req 4.5: se il testo del PDF non corrisponde al formato di alcun parser
  registrato, `spese.pdf.registry.rileva_parser` ritorna `None`, cosicché a
  monte non venga eseguito alcun salvataggio.

- Req 4.8: una transazione riconosciuta ma priva di data o di importo
  estraibile viene restituita da `estrai_movimenti_da_testo` come
  `TransazioneEstratta` con `motivo_esclusione` valorizzato e con `data` /
  `importo_eur` a `None` secondo il campo mancante.

I test lavorano sul core testuale puro alimentato con testo sintetico, senza
dipendere da file PDF o da `pdfplumber`.

Validates: Requirements 4.5, 4.8
"""

# Importa il package `spese.pdf` così da innescare la registrazione dei parser
# concreti (effetto collaterale dell'import di `revolut`), necessaria perché
# `rileva_parser` abbia parser registrati con cui confrontarsi (Req 4.4).
import spese.pdf  # noqa: F401
from spese.pdf.registry import rileva_parser
from spese.pdf.revolut import estrai_movimenti_da_testo


# ---------------------------------------------------------------------------
# Req 4.5: formato non riconosciuto -> rileva_parser ritorna None.
# ---------------------------------------------------------------------------
class TestFormatoNonRiconosciuto:
    def test_testo_non_corrispondente_ritorna_none(self):
        """Testo che non corrisponde ad alcun parser -> None (nessun salvataggio)."""
        testo = (
            "Banca Sconosciuta S.p.A.\n"
            "Lista movimenti del conto corrente\n"
            "01/01/2024  Pagamento POS  -10,00\n"
        )
        assert rileva_parser(testo) is None

    def test_testo_vuoto_ritorna_none(self):
        """Un testo vuoto non corrisponde ad alcun formato -> None."""
        assert rileva_parser("") is None

    def test_marcatori_parziali_non_bastano(self):
        """La presenza di solo alcuni marcatori non attiva il parser Revolut."""
        # Contiene "account statement" ma non "revolut": non deve riconoscere.
        testo = "Generic Bank account statement\n5 Jan 2024 Coffee 3.50 100.00\n"
        assert rileva_parser(testo) is None


# ---------------------------------------------------------------------------
# Req 4.8: transazione senza data/importo esclusa con motivo.
# ---------------------------------------------------------------------------
class TestEsclusioneConMotivo:
    def test_importo_mancante_esclusa_con_motivo(self):
        """Riga con data ma senza importo: esclusa, importo_eur None, data presente."""
        testo = "5 Jan 2024 Pagamento senza importo\n"
        transazioni = estrai_movimenti_da_testo(testo)

        assert len(transazioni) == 1
        t = transazioni[0]
        assert t.motivo_esclusione is not None
        assert t.importo_eur is None
        assert t.data is not None

    def test_data_mancante_esclusa_con_motivo(self):
        """Riga con importo ma data non estraibile: esclusa, data None, importo presente.

        Il token di mese ha la forma attesa (tre lettere) ma non è un mese
        riconosciuto: la riga è trattata come transazione, ma la data non è
        estraibile, quindi la transazione è esclusa con motivo mantenendo
        l'importo estratto (Req 4.8).
        """
        testo = "5 Zzz 2024 Descrizione 12.34 100.00\n"
        transazioni = estrai_movimenti_da_testo(testo)

        assert len(transazioni) == 1
        t = transazioni[0]
        assert t.motivo_esclusione is not None
        assert t.data is None
        assert t.importo_eur == 12.34

    def test_data_non_valida_ma_formato_data_valido_esclusa_con_motivo(self):
        """Data con mese valido ma giorno impossibile: esclusa con motivo, data None.

        Il mese ("Feb") è riconosciuto, quindi la riga è trattata come
        transazione, ma il 31 Feb non esiste: la data resta `None` e la
        transazione è esclusa con motivo, mantenendo l'importo estratto.
        """
        testo = "31 Feb 2024 Descrizione 12.34 100.00\n"
        transazioni = estrai_movimenti_da_testo(testo)

        assert len(transazioni) == 1
        t = transazioni[0]
        assert t.motivo_esclusione is not None
        assert t.data is None
        assert t.importo_eur == 12.34

    def test_transazione_valida_non_ha_motivo_esclusione(self):
        """Controllo di non-regressione: una riga completa non è esclusa."""
        testo = "5 Jan 2024 Coffee -3.50 100.00\n"
        transazioni = estrai_movimenti_da_testo(testo)

        assert len(transazioni) == 1
        t = transazioni[0]
        assert t.motivo_esclusione is None
        assert t.data is not None
        assert t.importo_eur == 3.50
        assert t.segno == "uscita"

create or replace view public.v_bond_summary as
with bond_tx as (
  select ticker, isin, descrizione, data_operazione,
         coalesce(quantita, 0) as nominale,
         importo_euro,
         (regexp_match(descrizione, '([0-9]+[.,][0-9]+)\s*%'))[1] as tasso_txt
  from transaction
  where ticker like 'M.%'
),
per_titolo as (
  select ticker,
         max(isin) as isin,
         max(descrizione) as descrizione,
         min(data_operazione) as prima_data_acquisto,
         sum(nominale) as nominale_totale,
         sum(abs(importo_euro)) as capitale_investito_eur,
         -- tasso cedolare fisso estratto dalla descrizione (NULL per indicizzati)
         max(replace(tasso_txt, ',', '.')::numeric) as tasso_cedolare_pct,
         -- cedole realmente incassate: transazioni positive (non acquisti). 0 se assenti.
         0::numeric as cedole_incassate_eur
  from bond_tx
  group by ticker
)
select
  ticker,
  isin,
  descrizione,
  prima_data_acquisto,
  nominale_totale,
  round(capitale_investito_eur, 2) as capitale_investito_eur,
  tasso_cedolare_pct,
  (current_date - prima_data_acquisto) as giorni_detenzione,
  -- cedola annua attesa (solo tasso fisso)
  round(case when tasso_cedolare_pct is not null
             then nominale_totale * tasso_cedolare_pct / 100.0 end, 2) as cedola_annua_attesa_eur,
  -- rateo cedole maturate dall'acquisto a oggi (solo tasso fisso), stima
  round(case when tasso_cedolare_pct is not null
             then nominale_totale * tasso_cedolare_pct / 100.0
                  * ((current_date - prima_data_acquisto)::numeric / 365.0) end, 2) as cedole_maturate_stimate_eur,
  cedole_incassate_eur
from per_titolo
order by prima_data_acquisto;;

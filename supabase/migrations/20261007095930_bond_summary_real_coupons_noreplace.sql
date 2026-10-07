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
  select ticker, max(isin) as isin, max(descrizione) as descrizione,
         min(data_operazione) as prima_data_acquisto,
         sum(nominale) as nominale_totale,
         sum(abs(importo_euro)) as capitale_investito_eur,
         max(replace(tasso_txt, ',', '.')::numeric) as tasso_cedolare_pct
  from bond_tx group by ticker
),
cedole_agg as (
  select isin, max(ticker) as ticker, max(descrizione) as descrizione,
         sum(importo_lordo_eur) as cedole_lorde_eur,
         sum(ritenuta_eur) as ritenute_eur,
         sum(importo_netto_eur) as cedole_incassate_eur,
         count(*) as n_cedole
  from bond_coupons group by isin
)
select
  coalesce(p.ticker, c.ticker)::varchar(10) as ticker,
  coalesce(p.isin, c.isin) as isin,
  coalesce(p.descrizione, c.descrizione) as descrizione,
  p.prima_data_acquisto,
  p.nominale_totale,
  round(p.capitale_investito_eur, 2) as capitale_investito_eur,
  p.tasso_cedolare_pct,
  (current_date - p.prima_data_acquisto) as giorni_detenzione,
  round(case when p.tasso_cedolare_pct is not null then p.nominale_totale * p.tasso_cedolare_pct / 100.0 end, 2) as cedola_annua_attesa_eur,
  round(case when p.tasso_cedolare_pct is not null then p.nominale_totale * p.tasso_cedolare_pct / 100.0 * ((current_date - p.prima_data_acquisto)::numeric / 365.0) end, 2) as cedole_maturate_stimate_eur,
  coalesce(round(c.cedole_incassate_eur, 2), 0) as cedole_incassate_eur,
  coalesce(round(c.cedole_lorde_eur, 2), 0) as cedole_lorde_eur,
  coalesce(round(c.ritenute_eur, 2), 0) as ritenute_eur,
  coalesce(c.n_cedole, 0) as n_cedole_incassate
from per_titolo p full outer join cedole_agg c on c.isin = p.isin
order by p.prima_data_acquisto nulls last;;

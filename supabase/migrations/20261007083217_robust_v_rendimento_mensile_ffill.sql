create or replace view public.v_portafoglio_rendimento_mensile as
with mesi as (
  select generate_series(
    date_trunc('month', (select min(data_operazione) from transaction)),
    date_trunc('month', current_date),
    interval '1 month'
  )::date as m
),
eom_price as (
  select ticker, date_trunc('month', date)::date as m, close,
         row_number() over (partition by ticker, date_trunc('month', date) order by date desc) as rn
  from etf_price_history
),
px as (select ticker, m, close from eom_price where rn = 1),
-- ticker effettivamente detenuti ogni mese (quote cumulate <> 0)
quote_cum as (
  select mi.m, t.ticker,
         sum(case when lower(t.tipo_operazione) like '%vend%' or lower(t.tipo_operazione) like '%rimbor%'
                  then -coalesce(t.quantita,0) else coalesce(t.quantita,0) end) as quote
  from mesi mi join transaction t
    on date_trunc('month', t.data_operazione) <= mi.m
   and t.protocollo = 0.0 and t.isin <> '0' and t.ticker not like 'M.%'
  group by mi.m, t.ticker
),
-- forward-fill: per ogni (ticker, mese) prende l'ultimo prezzo noto fino a quel mese
prezzo_ffill as (
  select q.m, q.ticker, q.quote,
         (select p.close from px p
           where p.ticker = q.ticker and p.m <= q.m
           order by p.m desc limit 1) as close_ff
  from quote_cum q
  where q.quote <> 0
),
nav as (
  select m, sum(quote * close_ff) as nav_eom
  from prezzo_ffill
  where close_ff is not null
  group by m
),
flows as (
  select date_trunc('month', data_operazione)::date as m,
         sum(case when lower(tipo_operazione) like '%vend%' or lower(tipo_operazione) like '%rimbor%'
                  then -abs(importo_euro) else abs(importo_euro) end) as flow
  from transaction
  where protocollo = 0.0 and isin <> '0' and ticker not like 'M.%'
  group by 1
),
serie as (
  select n.m, n.nav_eom, coalesce(f.flow, 0) as flusso_netto,
         lag(n.nav_eom) over (order by n.m) as nav_prec
  from nav n left join flows f on f.m = n.m
),
rendimenti as (
  select m, nav_eom, flusso_netto, nav_prec,
         case
           when nav_prec is null then (case when flusso_netto <> 0 then (nav_eom - flusso_netto)/flusso_netto else null end)
           when (nav_prec + flusso_netto) <> 0 then (nav_eom - nav_prec - flusso_netto)/(nav_prec + flusso_netto)
           else null
         end as r_mensile
  from serie
)
select extract(year from m)::int as anno,
       extract(month from m)::int as mese,
       to_char(m, 'YYYY-MM') as periodo,
       round(nav_eom, 2) as valore_fine_mese_eur,
       round(flusso_netto, 2) as flusso_netto_eur,
       round((coalesce(r_mensile,0)*100)::numeric, 2) as rendimento_mensile_pct,
       round(((exp(sum(ln(1+coalesce(r_mensile,0))) over (partition by extract(year from m) order by m))-1)*100)::numeric, 2) as rendimento_cumulato_ytd_pct
from rendimenti order by m;;

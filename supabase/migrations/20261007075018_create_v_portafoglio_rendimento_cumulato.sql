create or replace view public.v_portafoglio_rendimento_cumulato as
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
quote_cum as (
  select mi.m, t.ticker,
         sum(case when lower(t.tipo_operazione) like '%vend%' or lower(t.tipo_operazione) like '%rimbor%'
                  then -coalesce(t.quantita,0) else coalesce(t.quantita,0) end) as quote
  from mesi mi join transaction t
    on date_trunc('month', t.data_operazione) <= mi.m
   and t.protocollo = 0.0 and t.isin <> '0' and t.ticker not like 'M.%'
  group by mi.m, t.ticker
),
nav as (select q.m, sum(q.quote*p.close) nav_eom from quote_cum q join px p on p.ticker=q.ticker and p.m=q.m where q.quote<>0 group by q.m),
flows as (select date_trunc('month',data_operazione)::date m, sum(case when lower(tipo_operazione) like '%vend%' or lower(tipo_operazione) like '%rimbor%' then -abs(importo_euro) else abs(importo_euro) end) flow from transaction where protocollo=0.0 and isin<>'0' and ticker not like 'M.%' group by 1),
serie as (select n.m, n.nav_eom, coalesce(f.flow,0) flusso_netto, lag(n.nav_eom) over (order by n.m) nav_prec from nav n left join flows f on f.m=n.m),
rendimenti as (
  select m, case when nav_prec is null then (case when flusso_netto<>0 then (nav_eom-flusso_netto)/flusso_netto else null end)
                 when (nav_prec+flusso_netto)<>0 then (nav_eom-nav_prec-flusso_netto)/(nav_prec+flusso_netto) else null end as r_mensile
  from serie
)
select to_char(m,'YYYY-MM') periodo,
       extract(year from m)::int anno,
       extract(month from m)::int mese,
       round((exp(sum(ln(1+coalesce(r_mensile,0))) over (order by m))-1)*100::numeric,2) as rendimento_cumulato_totale_pct
from rendimenti order by m;;

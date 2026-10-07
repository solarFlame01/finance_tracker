create or replace view public.v_portafoglio_rendimento_annuo_twr as
with base as (
  select anno, mese, valore_fine_mese_eur, flusso_netto_eur, rendimento_mensile_pct
  from v_portafoglio_rendimento_mensile
),
agg as (
  select anno,
         round(((exp(sum(ln(1 + rendimento_mensile_pct/100.0))) - 1) * 100)::numeric, 2) as rendimento_annuo_pct,
         sum(flusso_netto_eur) as versato_anno_eur,
         count(*) as mesi_con_dati,
         max(mese) as ultimo_mese
  from base group by anno
),
fine_anno as (
  select distinct on (anno) anno, valore_fine_mese_eur as valore_fine_anno_eur
  from base order by anno, mese desc
)
select a.anno,
       a.rendimento_annuo_pct,
       f.valore_fine_anno_eur,
       a.versato_anno_eur,
       a.mesi_con_dati
from agg a join fine_anno f on f.anno = a.anno
order by a.anno;;

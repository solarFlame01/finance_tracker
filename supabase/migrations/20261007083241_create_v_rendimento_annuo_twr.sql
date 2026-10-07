create or replace view public.v_portafoglio_rendimento_annuo_twr as
select anno,
       round(((exp(sum(ln(1 + rendimento_mensile_pct/100.0))) - 1) * 100)::numeric, 2) as rendimento_annuo_pct,
       max(valore_fine_mese_eur) filter (where mese = (select max(m2.mese) from v_portafoglio_rendimento_mensile m2 where m2.anno = m.anno)) as valore_fine_anno_eur,
       sum(flusso_netto_eur) as versato_anno_eur,
       count(*) as mesi_con_dati
from v_portafoglio_rendimento_mensile m
group by anno
order by anno;;

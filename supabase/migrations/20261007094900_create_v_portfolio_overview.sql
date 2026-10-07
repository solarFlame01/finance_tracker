create or replace view public.v_portfolio_overview as
with etf as (
  select
    'ETF'::text as asset_class,
    coalesce(sum(costo_investito_eur), 0)::numeric  as investito_eur,
    coalesce(sum(market_value_attuale), 0)::numeric as valore_attuale_eur
  from v_portfolio_ticker_kpi
),
bond as (
  select
    'Obbligazioni'::text as asset_class,
    coalesce(sum(capitale_investito_eur), 0)::numeric as investito_eur,
    coalesce(sum(capitale_investito_eur), 0)::numeric as valore_attuale_eur
  from v_bond_summary
)
select
  asset_class,
  round(investito_eur, 2)       as investito_eur,
  round(valore_attuale_eur, 2)  as valore_attuale_eur,
  round(valore_attuale_eur - investito_eur, 2) as guadagno_eur,
  round(case when investito_eur > 0
             then (valore_attuale_eur - investito_eur) / investito_eur * 100 end, 2) as rendimento_pct
from (select * from etf union all select * from bond) t
order by asset_class;;

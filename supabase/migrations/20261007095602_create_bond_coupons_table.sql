create table if not exists public.bond_coupons (
  id bigint generated always as identity primary key,
  ticker varchar not null,
  isin varchar,
  descrizione varchar,
  data_operazione date not null,
  data_valuta date,
  importo_lordo_eur numeric not null default 0,
  ritenuta_eur numeric not null default 0,
  importo_netto_eur numeric not null default 0,
  protocollo_cedola varchar not null,
  protocollo_ritenuta varchar,
  created_at timestamp without time zone default now(),
  updated_at timestamp without time zone default now(),
  constraint bond_coupons_protocollo_cedola_key unique (protocollo_cedola)
);

comment on table public.bond_coupons is 'Cedole obbligazionarie incassate, estratte dai movimenti Directa. importo_netto = lordo - ritenuta.';

create index if not exists idx_bond_coupons_ticker on public.bond_coupons (ticker);
create index if not exists idx_bond_coupons_data on public.bond_coupons (data_operazione);;

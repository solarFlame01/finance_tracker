create table if not exists public.movimenti (
  id bigint generated always as identity primary key,
  data_movimento date not null,
  conto_id bigint not null references public.conti (id),
  importo_eur numeric not null,
  tipo_movimento varchar not null,
  valuta varchar not null default 'EUR',
  categoria_id bigint references public.categorie (id),
  sotto_categoria_id bigint references public.sotto_categorie (id),
  nota varchar,
  descrizione varchar,
  descrizione_normalizzata varchar not null,
  created_at timestamp without time zone default now(),
  updated_at timestamp without time zone default now(),
  constraint movimenti_tipo_movimento_check check (
    tipo_movimento in (
      'Spese', 'In', 'Trasferimento ingresso',
      'Trasferimento uscita', 'Aumento Saldo', 'Decremento Saldo'
    )
  ),
  constraint movimenti_chiave_naturale_key unique (
    data_movimento, conto_id, importo_eur, descrizione_normalizzata
  )
);
comment on table public.movimenti is 'Movimenti di spesa/entrata. Chiave naturale per upsert idempotente: data + conto + importo_eur + descrizione_normalizzata.';
create index if not exists idx_movimenti_data on public.movimenti (data_movimento);
create index if not exists idx_movimenti_conto on public.movimenti (conto_id);
create index if not exists idx_movimenti_categoria on public.movimenti (categoria_id);

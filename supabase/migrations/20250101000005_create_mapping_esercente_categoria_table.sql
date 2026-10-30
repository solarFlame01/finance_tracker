create table if not exists public.mapping_esercente_categoria (
  id bigint generated always as identity primary key,
  esercente_normalizzato varchar not null,
  categoria_id bigint not null references public.categorie (id),
  sotto_categoria_id bigint references public.sotto_categorie (id),
  created_at timestamp without time zone default now(),
  updated_at timestamp without time zone default now(),
  constraint mapping_esercente_key unique (esercente_normalizzato)
);
comment on table public.mapping_esercente_categoria is 'Mapping esercente normalizzato -> categoria/sotto-categoria di default per auto-categorizzazione.';
create index if not exists idx_mapping_esercente on public.mapping_esercente_categoria (esercente_normalizzato);

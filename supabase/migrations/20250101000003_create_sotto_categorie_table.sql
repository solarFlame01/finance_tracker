create table if not exists public.sotto_categorie (
  id bigint generated always as identity primary key,
  categoria_id bigint not null references public.categorie (id),
  nome varchar not null,
  created_at timestamp without time zone default now(),
  updated_at timestamp without time zone default now(),
  constraint sotto_categorie_cat_nome_key unique (categoria_id, nome),
  constraint sotto_categorie_nome_non_vuoto check (length(trim(nome)) > 0)
);
comment on table public.sotto_categorie is 'Sotto-categorie, ciascuna legata a una sola categoria.';
create index if not exists idx_sotto_categorie_categoria on public.sotto_categorie (categoria_id);

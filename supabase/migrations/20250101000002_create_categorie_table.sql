create table if not exists public.categorie (
  id bigint generated always as identity primary key,
  nome varchar not null,
  created_at timestamp without time zone default now(),
  updated_at timestamp without time zone default now(),
  constraint categorie_nome_key unique (nome),
  constraint categorie_nome_non_vuoto check (length(trim(nome)) > 0)
);
comment on table public.categorie is 'Categorie di classificazione dei movimenti di spesa.';

create table if not exists public.conti (
  id bigint generated always as identity primary key,
  nome varchar not null,
  created_at timestamp without time zone default now(),
  updated_at timestamp without time zone default now(),
  constraint conti_nome_key unique (nome),
  constraint conti_nome_non_vuoto check (length(trim(nome)) > 0)
);

comment on table public.conti is 'Conti finanziari dell''utente per la gestione spese.';

create index if not exists idx_conti_nome on public.conti (nome);

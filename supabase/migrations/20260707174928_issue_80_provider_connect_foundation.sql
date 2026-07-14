create table if not exists public.provider_connections (
  connection_id text primary key,
  provider_id text not null unique,
  provider_type text not null,
  auth_method text not null,
  status text not null,
  scopes jsonb not null default '[]'::jsonb,
  model_list jsonb not null default '[]'::jsonb,
  setup_url text not null default '',
  setup_instructions text not null default '',
  last_verified_at timestamptz,
  failure_reason text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists provider_connections_status_idx on public.provider_connections (status, updated_at);

create table if not exists public.provider_auth_flows (
  flow_id text primary key,
  provider_id text not null,
  auth_method text not null,
  status text not null,
  redirect_url text not null default '',
  state text not null default '',
  code_challenge text not null default '',
  code_challenge_method text not null default '',
  callback_received_at timestamptz,
  failure_reason text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists provider_auth_flows_provider_id_idx on public.provider_auth_flows (provider_id, created_at);;

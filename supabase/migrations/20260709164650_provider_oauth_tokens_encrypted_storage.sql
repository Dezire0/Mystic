create table if not exists public.provider_oauth_tokens (
  token_id text primary key,
  provider_id text not null unique,
  connection_id text not null,
  encrypted_access_token text not null,
  encrypted_refresh_token text not null default '',
  encrypted_id_token text not null default '',
  token_type text not null default '',
  scope_hash text not null default '',
  expires_at timestamptz,
  status text not null default 'connected',
  metadata_safe jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists provider_oauth_tokens_connection_id_idx on public.provider_oauth_tokens (connection_id, updated_at);

revoke all on table public.provider_oauth_tokens from anon, authenticated;
grant select, insert, update, delete on table public.provider_oauth_tokens to service_role;;

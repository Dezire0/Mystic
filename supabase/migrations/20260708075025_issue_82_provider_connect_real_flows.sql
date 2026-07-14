alter table public.provider_auth_flows
  add column if not exists authorization_url text not null default '';

alter table public.provider_auth_flows
  add column if not exists state_hash text not null default '';
;

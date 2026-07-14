create table if not exists public.model_calls (
  call_id text primary key,
  session_id text not null default '',
  provider_id text not null,
  model text not null default '',
  tool_name text not null,
  agent_role text not null default '',
  prompt_hash text not null,
  prompt_excerpt_safe text not null default '',
  output_text text not null default '',
  status text not null,
  error_type text not null default '',
  latency_ms integer not null default 0,
  usage_json jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists model_calls_session_id_idx on public.model_calls (session_id, created_at);
create index if not exists model_calls_provider_id_idx on public.model_calls (provider_id, created_at);;

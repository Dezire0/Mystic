-- Persistent runner presence is private operational state. Public clients only
-- learn availability through the Worker, never through direct table access.
create table if not exists public.lab_engine_runners (
  runner_id text primary key,
  runner_version text not null default '',
  engine_versions jsonb not null default '[]'::jsonb,
  resource_classes jsonb not null default '[]'::jsonb,
  status text not null default 'ready' check (status in ('ready', 'busy', 'offline', 'error')),
  current_job_id text not null default '',
  last_heartbeat timestamptz not null default timezone('utc', now()),
  completed_count bigint not null default 0,
  failed_count bigint not null default 0,
  safe_last_error text not null default '',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists lab_engine_runners_heartbeat_idx on public.lab_engine_runners(last_heartbeat desc);
alter table public.lab_engine_runners enable row level security;
revoke all on public.lab_engine_runners from anon, authenticated;
grant select, insert, update, delete on public.lab_engine_runners to service_role;

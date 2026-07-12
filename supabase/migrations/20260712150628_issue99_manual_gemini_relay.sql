-- Issue #99: user-controlled Gemini App Manual Relay. Service-role only; no RLS policy changes.
create table if not exists public.lab_orchestration_runs (
  run_id text primary key,
  session_id text not null references public.lab_sessions(session_id) on delete cascade,
  controller text not null default 'chatgpt',
  question text not null,
  status text not null,
  current_round text not null,
  provider_order jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  completed_at timestamptz,
  metadata_safe jsonb not null default '{}'::jsonb
);
create index if not exists lab_orchestration_runs_session_id_idx on public.lab_orchestration_runs (session_id, updated_at);

create table if not exists public.lab_orchestration_events (
  event_id text primary key,
  run_id text not null references public.lab_orchestration_runs(run_id) on delete cascade,
  sequence bigint not null,
  session_id text not null references public.lab_sessions(session_id) on delete cascade,
  provider_id text not null,
  provider_type text not null,
  agent_role text not null,
  round text not null,
  event_type text not null,
  full_visible_output text not null default '',
  structured_output jsonb not null default '{}'::jsonb,
  status text not null,
  created_at timestamptz not null default timezone('utc', now()),
  metadata_safe jsonb not null default '{}'::jsonb,
  unique (run_id, sequence)
);
create index if not exists lab_orchestration_events_run_sequence_idx on public.lab_orchestration_events (run_id, sequence);

create table if not exists public.lab_local_relay_jobs (
  job_id text primary key,
  run_id text not null references public.lab_orchestration_runs(run_id) on delete cascade,
  session_id text not null references public.lab_sessions(session_id) on delete cascade,
  provider_id text not null,
  agent_role text not null,
  round text not null,
  prompt_text text not null,
  context_safe jsonb not null default '{}'::jsonb,
  status text not null,
  response_text text not null default '',
  safe_error text not null default '',
  claimed_by text not null default '',
  created_at timestamptz not null default timezone('utc', now()),
  claimed_at timestamptz,
  completed_at timestamptz,
  expires_at timestamptz,
  metadata_safe jsonb not null default '{}'::jsonb
);
create index if not exists lab_local_relay_jobs_pending_created_idx on public.lab_local_relay_jobs (status, created_at);
create index if not exists lab_local_relay_jobs_run_id_idx on public.lab_local_relay_jobs (run_id, created_at);

revoke all on public.lab_orchestration_runs, public.lab_orchestration_events, public.lab_local_relay_jobs from anon, authenticated;
grant all on public.lab_orchestration_runs, public.lab_orchestration_events, public.lab_local_relay_jobs to service_role;

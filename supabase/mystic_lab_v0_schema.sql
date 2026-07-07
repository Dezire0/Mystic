create table if not exists public.lab_sessions (
  session_id text primary key,
  problem text not null,
  domain text not null,
  goal text not null,
  mode text not null,
  status text not null,
  current_phase text not null,
  active_room text not null,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  controller jsonb not null default '{}'::jsonb,
  participants jsonb not null default '[]'::jsonb,
  artifact_paths jsonb not null default '{}'::jsonb,
  next_actions jsonb not null default '[]'::jsonb,
  warnings jsonb not null default '[]'::jsonb,
  notebook_markdown text not null default '',
  experiments_json jsonb not null default '[]'::jsonb
);

create table if not exists public.lab_turns (
  turn_id text primary key,
  session_id text not null references public.lab_sessions(session_id) on delete cascade,
  phase text not null,
  room text not null,
  agent_role text not null,
  provider text not null,
  model_name text not null,
  input_summary text not null,
  output text not null,
  extracted_claims jsonb not null default '[]'::jsonb,
  requested_tools jsonb not null default '[]'::jsonb,
  tool_results jsonb not null default '[]'::jsonb,
  status text not null,
  error text not null default '',
  reply_to jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists lab_turns_session_id_idx on public.lab_turns (session_id, created_at);

create table if not exists public.claims (
  claim_id text primary key,
  session_id text not null references public.lab_sessions(session_id) on delete cascade,
  text text not null,
  claim_type text not null,
  status text not null,
  confidence text not null,
  source_turn_id text not null,
  supporting_evidence jsonb not null default '[]'::jsonb,
  refuting_evidence jsonb not null default '[]'::jsonb,
  related_experiments jsonb not null default '[]'::jsonb,
  related_failures jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists claims_session_id_idx on public.claims (session_id, created_at);

create table if not exists public.failures (
  failure_id text primary key,
  session_id text not null references public.lab_sessions(session_id) on delete cascade,
  claim_id text not null,
  source_turn_id text not null,
  first_fatal_error text not null,
  failure_type text not null,
  lesson text not null,
  reusable_as_training_data boolean not null default false,
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists failures_session_id_idx on public.failures (session_id, created_at);

create table if not exists public.memory_edges (
  edge_id text primary key,
  session_id text not null references public.lab_sessions(session_id) on delete cascade,
  from_id text not null,
  to_id text not null,
  relation text not null,
  evidence text not null,
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists memory_edges_session_id_idx on public.memory_edges (session_id, created_at);

create table if not exists public.reports (
  session_id text primary key references public.lab_sessions(session_id) on delete cascade,
  title text not null,
  problem text not null,
  domain text not null,
  surviving_claims jsonb not null default '[]'::jsonb,
  failed_claims jsonb not null default '[]'::jsonb,
  experiments jsonb not null default '[]'::jsonb,
  key_lessons jsonb not null default '[]'::jsonb,
  next_actions jsonb not null default '[]'::jsonb,
  markdown text not null default '',
  created_at timestamptz not null default timezone('utc', now())
);

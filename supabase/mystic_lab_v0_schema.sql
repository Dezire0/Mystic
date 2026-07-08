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

create table if not exists public.lab_scenes (
  scene_id text primary key,
  session_id text not null references public.lab_sessions(session_id) on delete cascade,
  domain text not null,
  title text not null,
  description text not null default '',
  units jsonb not null default '{}'::jsonb,
  parameters jsonb not null default '{}'::jsonb,
  attached_simulations jsonb not null default '[]'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  report_refs jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  artifact_paths jsonb not null default '{}'::jsonb,
  exports_json jsonb not null default '{}'::jsonb,
  report_markdown text not null default '',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists lab_scenes_session_id_idx on public.lab_scenes (session_id, updated_at);

create table if not exists public.lab_scene_objects (
  id text primary key,
  scene_id text not null references public.lab_scenes(scene_id) on delete cascade,
  type text not null,
  label text not null,
  position jsonb not null default '{"x":0,"y":0,"z":0}'::jsonb,
  rotation jsonb not null default '{"x":0,"y":0,"z":0}'::jsonb,
  scale jsonb not null default '{"x":1,"y":1,"z":1}'::jsonb,
  geometry jsonb not null default '{}'::jsonb,
  material jsonb not null default '{}'::jsonb,
  data jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists lab_scene_objects_scene_id_idx on public.lab_scene_objects (scene_id, created_at);

create table if not exists public.lab_simulations (
  simulation_id text primary key,
  scene_id text not null references public.lab_scenes(scene_id) on delete cascade,
  session_id text not null references public.lab_sessions(session_id) on delete cascade,
  adapter_id text not null,
  status text not null,
  inputs jsonb not null default '{}'::jsonb,
  outputs jsonb not null default '{}'::jsonb,
  evidence jsonb not null default '{}'::jsonb,
  warnings jsonb not null default '[]'::jsonb,
  errors jsonb not null default '[]'::jsonb,
  attached_object_ids jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists lab_simulations_scene_id_idx on public.lab_simulations (scene_id, created_at);

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
  authorization_url text not null default '',
  redirect_url text not null default '',
  state text not null default '',
  state_hash text not null default '',
  code_challenge text not null default '',
  code_challenge_method text not null default '',
  callback_received_at timestamptz,
  failure_reason text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists provider_auth_flows_provider_id_idx on public.provider_auth_flows (provider_id, created_at);

alter table public.provider_auth_flows
  add column if not exists authorization_url text not null default '';

alter table public.provider_auth_flows
  add column if not exists state_hash text not null default '';

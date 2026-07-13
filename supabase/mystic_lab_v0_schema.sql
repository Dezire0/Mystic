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
  revision bigint not null default 1,
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

create table if not exists public.lab_activity_events (
  event_id text primary key,
  event_type text not null,
  session_id text references public.lab_sessions(session_id) on delete cascade,
  scene_id text references public.lab_scenes(scene_id) on delete cascade,
  tool_name text not null,
  status text not null,
  safe_summary text not null,
  metadata_safe jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

alter table public.lab_activity_events enable row level security;
revoke all on table public.lab_activity_events from anon, authenticated;
grant select, insert on table public.lab_activity_events to service_role;
create index if not exists lab_activity_events_session_id_idx on public.lab_activity_events (session_id, created_at desc);
create index if not exists lab_activity_events_created_at_idx on public.lab_activity_events (created_at desc);
create index if not exists lab_activity_events_scene_id_idx on public.lab_activity_events (scene_id, created_at desc);

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
create index if not exists model_calls_provider_id_idx on public.model_calls (provider_id, created_at);

alter table public.provider_auth_flows
  add column if not exists authorization_url text not null default '';

alter table public.provider_auth_flows
  add column if not exists state_hash text not null default '';

create or replace function public.mystic_mutate_lab_scene(
  p_scene_id text,
  p_expected_revision bigint,
  p_scene jsonb,
  p_objects jsonb,
  p_simulations jsonb,
  p_activity jsonb default null
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_current_revision bigint;
  v_next_revision bigint;
begin
  select revision into v_current_revision from lab_scenes where scene_id = p_scene_id for update;
  if not found then return jsonb_build_object('error', 'scene_not_found'); end if;
  if v_current_revision <> p_expected_revision then
    return jsonb_build_object('error', 'scene_conflict', 'expected_revision', p_expected_revision, 'current_revision', v_current_revision, 'safe_message', 'The scene was changed by another client.');
  end if;
  v_next_revision := v_current_revision + 1;
  update lab_scenes set title = coalesce(p_scene->>'title', title), description = coalesce(p_scene->>'description', description), units = coalesce(p_scene->'units', units), parameters = coalesce(p_scene->'parameters', parameters), attached_simulations = coalesce(p_scene->'attached_simulations', attached_simulations), evidence_refs = coalesce(p_scene->'evidence_refs', evidence_refs), report_refs = coalesce(p_scene->'report_refs', report_refs), metadata = coalesce(p_scene->'metadata', metadata), artifact_paths = coalesce(p_scene->'artifact_paths', artifact_paths), exports_json = coalesce(p_scene->'exports_json', exports_json), report_markdown = coalesce(p_scene->>'report_markdown', report_markdown), revision = v_next_revision, updated_at = timezone('utc', now()) where scene_id = p_scene_id;
  delete from lab_scene_objects where scene_id = p_scene_id;
  if jsonb_array_length(coalesce(p_objects, '[]'::jsonb)) > 0 then insert into lab_scene_objects select * from jsonb_populate_recordset(null::lab_scene_objects, p_objects); end if;
  delete from lab_simulations where scene_id = p_scene_id;
  if jsonb_array_length(coalesce(p_simulations, '[]'::jsonb)) > 0 then insert into lab_simulations select * from jsonb_populate_recordset(null::lab_simulations, p_simulations); end if;
  if p_activity is not null then insert into lab_activity_events (event_id, event_type, session_id, scene_id, tool_name, status, safe_summary, metadata_safe) values (coalesce(p_activity->>'event_id', gen_random_uuid()::text), coalesce(p_activity->>'event_type', 'scene_mutation'), nullif(p_activity->>'session_id', ''), p_scene_id, coalesce(p_activity->>'tool_name', 'scene_mutation'), coalesce(p_activity->>'status', 'completed'), coalesce(p_activity->>'safe_summary', 'Scene changed.'), coalesce(p_activity->'metadata_safe', '{}'::jsonb)); end if;
  return jsonb_build_object('revision', v_next_revision, 'updated_at', timezone('utc', now()));
end;
$$;
revoke all on function public.mystic_mutate_lab_scene(text, bigint, jsonb, jsonb, jsonb, jsonb) from public, anon, authenticated;
grant execute on function public.mystic_mutate_lab_scene(text, bigint, jsonb, jsonb, jsonb, jsonb) to service_role;

create or replace function public.mystic_list_lab_scenes(p_limit integer default 50, p_session_id text default null, p_updated_after timestamptz default null)
returns table(scene_id text, session_id text, title text, description text, object_count integer, simulation_count integer, revision bigint, created_at timestamptz, updated_at timestamptz)
language sql security definer set search_path = public
as $$
  select scene.scene_id, scene.session_id, scene.title, scene.description, count(distinct object.id)::integer, count(distinct simulation.simulation_id)::integer, scene.revision, scene.created_at, scene.updated_at
  from public.lab_scenes as scene
  left join public.lab_scene_objects as object on object.scene_id = scene.scene_id
  left join public.lab_simulations as simulation on simulation.scene_id = scene.scene_id
  where (p_session_id is null or scene.session_id = p_session_id) and (p_updated_after is null or scene.updated_at > p_updated_after)
  group by scene.scene_id order by scene.updated_at desc limit greatest(1, least(coalesce(p_limit, 50), 100));
$$;
revoke all on function public.mystic_list_lab_scenes(integer, text, timestamptz) from public, anon, authenticated;
grant execute on function public.mystic_list_lab_scenes(integer, text, timestamptz) to service_role;

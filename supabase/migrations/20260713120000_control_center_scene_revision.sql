-- Mystic Control Center Phase 1: authoritative listings, audit events, and
-- atomic scene replacement guarded by an optimistic revision number.
alter table public.lab_scenes add column if not exists revision bigint not null default 1;

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

create index if not exists lab_activity_events_created_at_idx on public.lab_activity_events (created_at desc);
create index if not exists lab_activity_events_scene_id_idx on public.lab_activity_events (scene_id, created_at desc);

-- This is an internal audit stream. The browser never receives a Supabase key;
-- only the Worker service role may access it through the MCP gateway.
alter table public.lab_activity_events enable row level security;
revoke all on table public.lab_activity_events from anon, authenticated;
grant select, insert on table public.lab_activity_events to service_role;

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
  if not found then
    return jsonb_build_object('error', 'scene_not_found');
  end if;
  if v_current_revision <> p_expected_revision then
    return jsonb_build_object(
      'error', 'scene_conflict',
      'expected_revision', p_expected_revision,
      'current_revision', v_current_revision,
      'safe_message', 'The scene was changed by another client.'
    );
  end if;

  v_next_revision := v_current_revision + 1;
  update lab_scenes set
    title = coalesce(p_scene->>'title', title),
    description = coalesce(p_scene->>'description', description),
    units = coalesce(p_scene->'units', units),
    parameters = coalesce(p_scene->'parameters', parameters),
    attached_simulations = coalesce(p_scene->'attached_simulations', attached_simulations),
    evidence_refs = coalesce(p_scene->'evidence_refs', evidence_refs),
    report_refs = coalesce(p_scene->'report_refs', report_refs),
    metadata = coalesce(p_scene->'metadata', metadata),
    artifact_paths = coalesce(p_scene->'artifact_paths', artifact_paths),
    exports_json = coalesce(p_scene->'exports_json', exports_json),
    report_markdown = coalesce(p_scene->>'report_markdown', report_markdown),
    revision = v_next_revision,
    updated_at = timezone('utc', now())
  where scene_id = p_scene_id;

  delete from lab_scene_objects where scene_id = p_scene_id;
  if jsonb_array_length(coalesce(p_objects, '[]'::jsonb)) > 0 then
    insert into lab_scene_objects
    select * from jsonb_populate_recordset(null::lab_scene_objects, p_objects);
  end if;
  delete from lab_simulations where scene_id = p_scene_id;
  if jsonb_array_length(coalesce(p_simulations, '[]'::jsonb)) > 0 then
    insert into lab_simulations
    select * from jsonb_populate_recordset(null::lab_simulations, p_simulations);
  end if;
  if p_activity is not null then
    insert into lab_activity_events (event_id, event_type, session_id, scene_id, tool_name, status, safe_summary, metadata_safe)
    values (
      coalesce(p_activity->>'event_id', gen_random_uuid()::text),
      coalesce(p_activity->>'event_type', 'scene_mutation'),
      nullif(p_activity->>'session_id', ''),
      p_scene_id,
      coalesce(p_activity->>'tool_name', 'scene_mutation'),
      coalesce(p_activity->>'status', 'completed'),
      coalesce(p_activity->>'safe_summary', 'Scene changed.'),
      coalesce(p_activity->'metadata_safe', '{}'::jsonb)
    );
  end if;
  return jsonb_build_object('revision', v_next_revision, 'updated_at', timezone('utc', now()));
end;
$$;

revoke all on function public.mystic_mutate_lab_scene(text, bigint, jsonb, jsonb, jsonb, jsonb) from public;
revoke all on function public.mystic_mutate_lab_scene(text, bigint, jsonb, jsonb, jsonb, jsonb) from anon, authenticated;
grant execute on function public.mystic_mutate_lab_scene(text, bigint, jsonb, jsonb, jsonb, jsonb) to service_role;

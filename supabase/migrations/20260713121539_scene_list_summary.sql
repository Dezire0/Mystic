-- Return scene summaries in one authoritative query rather than fan-out REST
-- requests; the function is only callable by the Mystic Worker service role.
create or replace function public.mystic_list_lab_scenes(
  p_limit integer default 50,
  p_session_id text default null,
  p_updated_after timestamptz default null
) returns table(
  scene_id text,
  session_id text,
  title text,
  description text,
  object_count integer,
  simulation_count integer,
  revision bigint,
  created_at timestamptz,
  updated_at timestamptz
)
language sql
security definer
set search_path = public
as $$
  select
    scene.scene_id,
    scene.session_id,
    scene.title,
    scene.description,
    count(distinct object.id)::integer as object_count,
    count(distinct simulation.simulation_id)::integer as simulation_count,
    scene.revision,
    scene.created_at,
    scene.updated_at
  from public.lab_scenes as scene
  left join public.lab_scene_objects as object on object.scene_id = scene.scene_id
  left join public.lab_simulations as simulation on simulation.scene_id = scene.scene_id
  where (p_session_id is null or scene.session_id = p_session_id)
    and (p_updated_after is null or scene.updated_at > p_updated_after)
  group by scene.scene_id
  order by scene.updated_at desc
  limit greatest(1, least(coalesce(p_limit, 50), 100));
$$;

revoke all on function public.mystic_list_lab_scenes(integer, text, timestamptz) from public;
revoke all on function public.mystic_list_lab_scenes(integer, text, timestamptz) from anon, authenticated;
grant execute on function public.mystic_list_lab_scenes(integer, text, timestamptz) to service_role;

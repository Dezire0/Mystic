-- Phase 2C.1: additive durable research-campaign runtime.
create table if not exists public.lab_research_campaigns (
  campaign_id text primary key,
  title text not null check (char_length(title) between 1 and 240),
  description text not null default '' check (char_length(description) <= 8000),
  domain text not null default 'general' check (char_length(domain) between 1 and 80),
  phase text not null default 'PLANNING' check (phase in (
    'PLANNING','BACKGROUND_RESEARCH','KNOWLEDGE_GRAPH','HYPOTHESIS_GENERATION',
    'MODEL_SELECTION','EXPERIMENT_PLANNING','ENGINE_EXECUTION','RESULT_VALIDATION',
    'REFEREE_REVIEW','FAILURE_ARCHIVE','KNOWLEDGE_UPDATE','NEXT_ACTION','REPORT','COMPLETE'
  )),
  status text not null default 'ACTIVE' check (status in ('ACTIVE','PAUSED','FAILED','CANCELLED','COMPLETE')),
  revision bigint not null default 0 check (revision >= 0),
  iteration integer not null default 0 check (iteration >= 0),
  metadata jsonb not null default '{}'::jsonb,
  goals jsonb not null default '[]'::jsonb,
  questions jsonb not null default '[]'::jsonb,
  hypotheses jsonb not null default '[]'::jsonb,
  evidence jsonb not null default '[]'::jsonb,
  experiments jsonb not null default '[]'::jsonb,
  models jsonb not null default '[]'::jsonb,
  reviews jsonb not null default '[]'::jsonb,
  failures jsonb not null default '[]'::jsonb,
  decisions jsonb not null default '[]'::jsonb,
  artifacts jsonb not null default '[]'::jsonb,
  budget jsonb not null default '{}'::jsonb,
  statistics jsonb not null default '{}'::jsonb,
  runtime jsonb not null default '{}'::jsonb,
  idempotency_records jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.lab_campaign_knowledge_nodes (
  campaign_id text not null references public.lab_research_campaigns(campaign_id) on delete cascade,
  node_id text not null,
  version integer not null check (version >= 1),
  node_type text not null check (node_type in ('claim','evidence','model','hypothesis','experiment','failure','citation','artifact')),
  payload jsonb not null default '{}'::jsonb,
  supersedes_version integer,
  content_hash text not null check (char_length(content_hash) = 64),
  created_at timestamptz not null default timezone('utc', now()),
  primary key (campaign_id, node_id, version),
  check (supersedes_version is null or supersedes_version < version)
);

create table if not exists public.lab_campaign_knowledge_edges (
  edge_id text primary key,
  campaign_id text not null references public.lab_research_campaigns(campaign_id) on delete cascade,
  from_node_id text not null,
  to_node_id text not null,
  relation text not null check (relation in ('supports','refutes','uses_model','tests','cites','depends_on','caused_failure','supersedes','derived_from')),
  version integer not null default 1 check (version >= 1),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  check (from_node_id <> to_node_id or relation = 'supersedes')
);

create table if not exists public.lab_campaign_timeline (
  event_id text primary key,
  campaign_id text not null references public.lab_research_campaigns(campaign_id) on delete cascade,
  event_type text not null,
  phase text not null,
  status text not null,
  summary text not null check (char_length(summary) <= 1000),
  revision bigint not null check (revision >= 0),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.lab_campaign_checkpoints (
  checkpoint_id text primary key,
  campaign_id text not null references public.lab_research_campaigns(campaign_id) on delete cascade,
  label text not null check (char_length(label) between 1 and 160),
  iteration integer not null check (iteration >= 0),
  phase text not null,
  status text not null,
  revision bigint not null check (revision >= 0),
  state_snapshot jsonb not null,
  graph_snapshot jsonb not null,
  metadata jsonb not null default '{}'::jsonb,
  timing jsonb not null default '{}'::jsonb,
  engine_versions jsonb not null default '{}'::jsonb,
  runner_versions jsonb not null default '{}'::jsonb,
  hashes jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists lab_research_campaigns_updated_idx on public.lab_research_campaigns(updated_at desc);
create index if not exists lab_research_campaigns_status_idx on public.lab_research_campaigns(status, updated_at desc);
create index if not exists lab_campaign_nodes_latest_idx on public.lab_campaign_knowledge_nodes(campaign_id, node_id, version desc);
create index if not exists lab_campaign_edges_campaign_idx on public.lab_campaign_knowledge_edges(campaign_id, created_at);
create index if not exists lab_campaign_timeline_campaign_idx on public.lab_campaign_timeline(campaign_id, created_at);
create index if not exists lab_campaign_checkpoints_campaign_idx on public.lab_campaign_checkpoints(campaign_id, created_at desc);

alter table public.lab_research_campaigns enable row level security;
alter table public.lab_campaign_knowledge_nodes enable row level security;
alter table public.lab_campaign_knowledge_edges enable row level security;
alter table public.lab_campaign_timeline enable row level security;
alter table public.lab_campaign_checkpoints enable row level security;
revoke all on public.lab_research_campaigns, public.lab_campaign_knowledge_nodes,
  public.lab_campaign_knowledge_edges, public.lab_campaign_timeline,
  public.lab_campaign_checkpoints from anon, authenticated;
grant select, insert, update, delete on public.lab_research_campaigns,
  public.lab_campaign_knowledge_nodes, public.lab_campaign_knowledge_edges,
  public.lab_campaign_timeline, public.lab_campaign_checkpoints to service_role;

create or replace function public.mystic_set_research_campaign_status(
  p_campaign_id text,
  p_operation text,
  p_idempotency_key text default ''
) returns public.lab_research_campaigns
language plpgsql security definer set search_path = public as $$
declare
  current_row public.lab_research_campaigns;
  target_status text;
  allowed boolean := false;
  next_revision bigint;
begin
  select * into current_row from public.lab_research_campaigns
    where campaign_id = p_campaign_id for update;
  if not found then raise exception 'campaign_not_found'; end if;
  if p_idempotency_key <> '' and current_row.idempotency_records ? p_idempotency_key then
    if current_row.idempotency_records->p_idempotency_key->>'operation' <> p_operation then
      raise exception 'campaign_idempotency_conflict';
    end if;
    return current_row;
  end if;
  if p_operation = 'pause' then target_status := 'PAUSED'; allowed := current_row.status = 'ACTIVE';
  elsif p_operation = 'resume' then target_status := 'ACTIVE'; allowed := current_row.status = 'PAUSED';
  elsif p_operation = 'cancel' then target_status := 'CANCELLED'; allowed := current_row.status in ('ACTIVE','PAUSED','FAILED');
  else raise exception 'campaign_operation_invalid'; end if;
  if not allowed then raise exception 'campaign_transition_invalid'; end if;
  next_revision := current_row.revision + 1;
  update public.lab_research_campaigns set
    status = target_status,
    revision = next_revision,
    updated_at = timezone('utc', now()),
    idempotency_records = case when p_idempotency_key = '' then idempotency_records else
      idempotency_records || jsonb_build_object(p_idempotency_key, jsonb_build_object('operation', p_operation, 'revision', next_revision)) end
    where campaign_id = p_campaign_id returning * into current_row;
  insert into public.lab_campaign_timeline(event_id,campaign_id,event_type,phase,status,summary,revision,metadata)
    values ('event_' || replace(gen_random_uuid()::text,'-',''), p_campaign_id,
      'CAMPAIGN_' || upper(p_operation), current_row.phase, current_row.status,
      'Research campaign ' || p_operation || ' accepted.', current_row.revision, '{}'::jsonb);
  return current_row;
end $$;

create or replace function public.mystic_checkpoint_research_campaign(
  p_campaign_id text,
  p_expected_revision bigint,
  p_checkpoint jsonb,
  p_idempotency_key text default ''
) returns public.lab_research_campaigns
language plpgsql security definer set search_path = public as $$
declare current_row public.lab_research_campaigns; next_revision bigint;
begin
  select * into current_row from public.lab_research_campaigns where campaign_id=p_campaign_id for update;
  if not found then raise exception 'campaign_not_found'; end if;
  if p_idempotency_key <> '' and current_row.idempotency_records ? p_idempotency_key then return current_row; end if;
  if current_row.revision <> p_expected_revision then raise exception 'campaign_revision_conflict'; end if;
  if (select count(*) from public.lab_campaign_checkpoints where campaign_id=p_campaign_id) >=
    greatest(1, least(1000, coalesce((current_row.budget->>'max_checkpoints')::integer,100))) then
    raise exception 'campaign_checkpoint_budget_exhausted';
  end if;
  insert into public.lab_campaign_checkpoints(
    checkpoint_id,campaign_id,label,iteration,phase,status,revision,state_snapshot,graph_snapshot,
    metadata,timing,engine_versions,runner_versions,hashes,created_at)
  values (
    p_checkpoint->>'checkpoint_id',p_campaign_id,p_checkpoint->>'label',
    coalesce((p_checkpoint->>'iteration')::integer,0),p_checkpoint->>'phase',p_checkpoint->>'status',
    coalesce((p_checkpoint->>'revision')::bigint,current_row.revision),p_checkpoint->'state_snapshot',
    p_checkpoint->'graph_snapshot',coalesce(p_checkpoint->'metadata','{}'::jsonb),
    coalesce(p_checkpoint->'timing','{}'::jsonb),coalesce(p_checkpoint->'engine_versions','{}'::jsonb),
    coalesce(p_checkpoint->'runner_versions','{}'::jsonb),p_checkpoint->'hashes',
    coalesce((p_checkpoint->>'created_at')::timestamptz,timezone('utc',now())));
  next_revision := current_row.revision + 1;
  update public.lab_research_campaigns set revision=next_revision, updated_at=timezone('utc',now()),
    statistics=jsonb_set(statistics,'{checkpoint_count}',to_jsonb(coalesce((statistics->>'checkpoint_count')::integer,0)+1),true),
    runtime=jsonb_set(runtime,'{last_checkpoint_id}',to_jsonb(p_checkpoint->>'checkpoint_id'),true),
    idempotency_records=case when p_idempotency_key='' then idempotency_records else
      idempotency_records || jsonb_build_object(p_idempotency_key,jsonb_build_object('operation','checkpoint','revision',next_revision)) end
    where campaign_id=p_campaign_id returning * into current_row;
  insert into public.lab_campaign_timeline(event_id,campaign_id,event_type,phase,status,summary,revision,metadata)
    values ('event_' || replace(gen_random_uuid()::text,'-',''),p_campaign_id,'CHECKPOINT_CREATED',current_row.phase,
      current_row.status,'Campaign checkpoint created.',current_row.revision,
      jsonb_build_object('checkpoint_id',p_checkpoint->>'checkpoint_id'));
  return current_row;
end $$;

revoke all on function public.mystic_set_research_campaign_status(text,text,text) from public, anon, authenticated;
revoke all on function public.mystic_checkpoint_research_campaign(text,bigint,jsonb,text) from public, anon, authenticated;
grant execute on function public.mystic_set_research_campaign_status(text,text,text) to service_role;
grant execute on function public.mystic_checkpoint_research_campaign(text,bigint,jsonb,text) to service_role;
